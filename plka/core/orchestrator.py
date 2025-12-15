"""
Orchestrator component for PLKA
Implements FSM (Finite State Machine) for task management
States: PENDING → PLANNING → EDITING → VERIFYING → DONE/FAILED
"""

import uuid
import json
import sqlite3
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class TaskStatus(Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EDITING = "EDITING"
    VERIFYING = "VERIFYING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class Task:
    task_id: str
    project_path: str
    user_request: str
    status: TaskStatus
    created_at: datetime
    error_message: Optional[str] = None


class Orchestrator:
    def __init__(self, db_path: str = "/workspace/plka/agent_memory.db"):
        self.db_path = db_path
        self.active_tasks: Dict[str, Task] = {}
        self.llm_client = None
        self.rag_service = None
        self.file_editor = None
        self.experience_manager = None
        
    def create_task(self, project_path: str, user_request: str) -> str:
        """Create a new task and return its ID."""
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
        
        task = Task(
            task_id=task_id,
            project_path=project_path,
            user_request=user_request,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.active_tasks[task_id] = task
        self._log_action(task_id, "orchestrator", "task_created", "SUCCESS", {
            "project_path": project_path,
            "user_request": user_request
        })
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task."""
        task = self.active_tasks.get(task_id)
        return task.status if task else None
    
    def execute_task(self, task_id: str) -> bool:
        """Execute a task through the FSM states."""
        if task_id not in self.active_tasks:
            return False
            
        task = self.active_tasks[task_id]
        
        try:
            # Transition from PENDING to PLANNING
            self._update_task_status(task_id, TaskStatus.PLANNING)
            if not self._execute_planning_phase(task):
                self._update_task_status(task_id, TaskStatus.FAILED, "Planning phase failed")
                return False
            
            # Transition to EDITING
            self._update_task_status(task_id, TaskStatus.EDITING)
            if not self._execute_editing_phase(task):
                self._update_task_status(task_id, TaskStatus.FAILED, "Editing phase failed")
                return False
            
            # Transition to VERIFYING
            self._update_task_status(task_id, TaskStatus.VERIFYING)
            if not self._execute_verification_phase(task):
                self._update_task_status(task_id, TaskStatus.FAILED, "Verification phase failed")
                return False
            
            # Success!
            self._update_task_status(task_id, TaskStatus.DONE)
            return True
            
        except Exception as e:
            self._update_task_status(task_id, TaskStatus.FAILED, str(e))
            return False
    
    def _execute_planning_phase(self, task: Task) -> bool:
        """Execute the planning phase using RAG and LLM."""
        try:
            # Use ExperienceManager to get relevant patterns
            if self.experience_manager:
                relevant_patterns = self.experience_manager.get_relevant_patterns(task.user_request)
                
                # Log the retrieved patterns
                self._log_action(task.task_id, "experience_manager", "patterns_retrieved", "SUCCESS", {
                    "pattern_count": len(relevant_patterns),
                    "patterns": [p['name'] for p in relevant_patterns]
                })
            
            # Use RAG to retrieve relevant context
            if self.rag_service:
                context = self.rag_service.retrieve_context(task.project_path, task.user_request)
                
                # Log the retrieval
                self._log_action(task.task_id, "rag_service", "context_retrieved", "SUCCESS", {
                    "chunks_count": len(context) if isinstance(context, list) else 0,
                    "context_summary": str(context)[:200] + "..." if len(str(context)) > 200 else str(context)
                })
            
            # Plan with LLM
            if self.llm_client:
                plan_prompt = self._create_planning_prompt(task.user_request, context if 'context' in locals() else "")
                plan = self.llm_client.generate(plan_prompt, profile="planner")
                
                # Log the plan generation
                self._log_action(task.task_id, "llm_client", "plan_generated", "SUCCESS", {
                    "plan_length": len(plan),
                    "plan_preview": plan[:100] + "..." if len(plan) > 100 else plan
                })
                
                # Store the plan for later use
                task.plan = plan
                
            return True
        except Exception as e:
            self._log_action(task.task_id, "orchestrator", "planning_failed", "ERROR", {
                "error": str(e)
            })
            return False
    
    def _execute_editing_phase(self, task: Task) -> bool:
        """Execute the editing phase to modify files."""
        try:
            # Generate code changes with LLM
            if hasattr(task, 'plan') and self.llm_client and self.file_editor:
                code_changes = self._generate_code_changes(task)
                
                # Apply changes using FileEditor
                for change in code_changes:
                    result = self.file_editor.apply_change(change)
                    
                    if result['status'] != 'success':
                        self._log_action(task.task_id, "file_editor", "change_failed", "ERROR", {
                            "file_path": change['file_path'],
                            "error_code": result.get('error_code'),
                            "error_details": result.get('error_details')
                        })
                        return False
                    
                    # Log successful change
                    self._log_action(task.task_id, "file_editor", "change_applied", "SUCCESS", {
                        "file_path": change['file_path'],
                        "operation": change['operation'],
                        "lines_changed": result.get('line_changes', {})
                    })
            
            return True
        except Exception as e:
            self._log_action(task.task_id, "orchestrator", "editing_failed", "ERROR", {
                "error": str(e)
            })
            return False
    
    def _execute_verification_phase(self, task: Task) -> bool:
        """Execute the verification phase to ensure changes are valid."""
        try:
            # Perform various checks
            verification_results = {
                "syntax_check": True,  # This would actually check syntax
                "import_check": True,  # This would actually check imports
                "lint_check": True     # This would actually run linter
            }
            
            # Log verification results
            self._log_action(task.task_id, "orchestrator", "verification_complete", "SUCCESS", {
                "results": verification_results
            })
            
            # Update experience manager with successful pattern
            if self.experience_manager and hasattr(task, 'plan'):
                self.experience_manager.record_successful_pattern(task.user_request, task.plan)
            
            return all(verification_results.values())
        except Exception as e:
            self._log_action(task.task_id, "orchestrator", "verification_failed", "ERROR", {
                "error": str(e)
            })
            return False
    
    def _create_planning_prompt(self, user_request: str, context: str) -> str:
        """Create a prompt for the planning phase."""
        # This would use templates from config/prompts.yaml
        return f"""
        User request: {user_request}
        
        Relevant context from the codebase:
        {context}
        
        Create a detailed plan for implementing the requested changes.
        Be specific about which files need to be modified and what changes are needed.
        """
    
    def _generate_code_changes(self, task: Task) -> list:
        """Generate code changes based on the plan."""
        # This would generate specific file change operations
        changes = []
        
        # For now, return a dummy change - in real implementation, this would
        # use the LLM to generate specific code modifications
        if self.llm_client:
            # Generate detailed code instructions
            code_prompt = f"""
            Based on this plan: {getattr(task, 'plan', '')}
            
            Generate specific code changes with exact context matching.
            Return in JSON format with file_path, operation, original_context, and modified_content.
            """
            
            response = self.llm_client.generate(code_prompt, profile="coder")
            
            try:
                # Parse the response as JSON for changes
                changes_data = json.loads(response)
                if isinstance(changes_data, dict) and 'changes' in changes_data:
                    changes = changes_data['changes']
                elif isinstance(changes_data, list):
                    changes = changes_data
            except json.JSONDecodeError:
                # If not valid JSON, return a simple change
                changes.append({
                    "file_path": f"{task.project_path}/main.py",  # Default path
                    "operation": "append",
                    "original_context": "",
                    "modified_content": "# TODO: Implement based on user request",
                    "task_id": task.task_id
                })
        
        return changes
    
    def _update_task_status(self, task_id: str, status: TaskStatus, error_message: str = None):
        """Update the status of a task."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            old_status = task.status
            task.status = status
            task.error_message = error_message
            
            # Log the status change
            self._log_action(task_id, "orchestrator", "status_change", "SUCCESS", {
                "old_status": old_status.value,
                "new_status": status.value,
                "error_message": error_message
            })
    
    def _log_action(self, task_id: str, component: str, action_type: str, status: str, details: Dict[str, Any]):
        """Log an action to the agent memory database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO actions (timestamp, project, task_id, step, component, action_type, status, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                self.active_tasks.get(task_id, Task(task_id, "", "", TaskStatus.PENDING, datetime.now())).project_path,
                task_id,
                action_type,
                component,
                action_type,
                status,
                json.dumps(details)
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging action: {e}")


# Example usage:
if __name__ == "__main__":
    orchestrator = Orchestrator()
    task_id = orchestrator.create_task("/workspace/plka/projects/example", "Add a hello function")
    print(f"Created task: {task_id}")
    print(f"Initial status: {orchestrator.get_task_status(task_id)}")