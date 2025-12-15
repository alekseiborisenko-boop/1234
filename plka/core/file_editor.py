"""
FileEditor component for PLKA
Handles precise file editing with AST validation, syntax checking, and safety measures
"""

import os
import ast
import py_compile
import difflib
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple
from datetime import datetime
import tempfile
import subprocess
import re


class PathValidator:
    """Validates file paths to ensure they're within allowed directories."""
    
    def __init__(self, base_path: str = "/workspace/plka"):
        self.base_path = Path(base_path).resolve()
    
    def is_valid_path(self, path: str) -> bool:
        """Check if a path is valid and safe."""
        path_obj = Path(path).resolve()
        
        # Check if path is within base directory
        try:
            path_obj.relative_to(self.base_path)
        except ValueError:
            return False
        
        # Check for dangerous patterns
        if ".." in path:
            return False
        
        # Check if it's a symbolic link (which could lead outside allowed paths)
        if path_obj.is_symlink():
            return False
        
        return True


class FileEditor:
    def __init__(self, base_path: str = "/workspace/plka", enable_linter: bool = True):
        self.validator = PathValidator(base_path)
        self.enable_linter = enable_linter
        self.snapshots_dir = Path(base_path) / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def apply_change(self, change_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a change to a file based on the specification.
        
        Args:
            change_spec: Dictionary with keys:
                - file_path: path to the file
                - operation: 'insert', 'replace', 'delete_block', 'append'
                - original_context: original content that should match
                - modified_content: new content to apply
                - task_id: associated task ID
        
        Returns:
            Dictionary with result of the operation
        """
        try:
            # Validate path
            file_path = change_spec['file_path']
            if not self.validator.is_valid_path(file_path):
                return {
                    'status': 'error',
                    'error_code': 'invalid_path',
                    'error_details': f'Path not allowed: {file_path}'
                }
            
            # Check if file exists
            path_obj = Path(file_path)
            if not path_obj.exists():
                # If operation is append and file doesn't exist, create it
                if change_spec['operation'] == 'append':
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                    path_obj.touch()
                else:
                    return {
                        'status': 'error',
                        'error_code': 'file_not_found',
                        'error_details': f'File does not exist: {file_path}'
                    }
            
            # Read current file content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Create snapshot before modifying
            snapshot_path = self._create_snapshot(file_path, change_spec.get('task_id', 'unknown'))
            
            # Apply the change based on operation type
            if change_spec['operation'] == 'replace':
                new_content = self._apply_replace_operation(original_content, change_spec)
            elif change_spec['operation'] == 'insert':
                new_content = self._apply_insert_operation(original_content, change_spec)
            elif change_spec['operation'] == 'delete_block':
                new_content = self._apply_delete_operation(original_content, change_spec)
            elif change_spec['operation'] == 'append':
                new_content = self._apply_append_operation(original_content, change_spec)
            else:
                return {
                    'status': 'error',
                    'error_code': 'unsupported_operation',
                    'error_details': f'Unsupported operation: {change_spec["operation"]}'
                }
            
            if new_content is None:
                return {
                    'status': 'error',
                    'error_code': 'context_not_found',
                    'error_details': 'Original context not found in file'
                }
            
            # Validate the change
            validation_result = self._validate_change(new_content, file_path)
            if not validation_result['valid']:
                # Restore from snapshot
                self._restore_from_snapshot(snapshot_path, file_path)
                return {
                    'status': 'error',
                    'error_code': validation_result['error_code'],
                    'error_details': validation_result['details']
                }
            
            # Write the new content to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Calculate changes
            original_lines = original_content.splitlines()
            new_lines = new_content.splitlines()
            line_changes = {
                'added': len([l for l in difflib.unified_diff(original_lines, new_lines) if l.startswith('+')]) - 1,  # -1 to account for diff header
                'removed': len([l for l in difflib.unified_diff(original_lines, new_lines) if l.startswith('-')]) - 1  # -1 to account for diff header
            }
            
            return {
                'status': 'success',
                'snapshot_path': snapshot_path,
                'new_content_preview': new_content[:200] + ('...' if len(new_content) > 200 else ''),
                'line_changes': line_changes
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error_code': 'exception',
                'error_details': str(e)
            }
    
    def _apply_replace_operation(self, original_content: str, change_spec: Dict[str, Any]) -> str:
        """Apply a replace operation."""
        original_context = change_spec['original_context']
        modified_content = change_spec['modified_content']
        
        # Find the original context in the file content
        if original_context not in original_content:
            # Try fuzzy matching
            best_match = self._find_best_fuzzy_match(original_content, original_context)
            if best_match:
                start, end = best_match
                return original_content[:start] + modified_content + original_content[end:]
            return None
        
        # Replace the first occurrence of original_context with modified_content
        return original_content.replace(original_context, modified_content, 1)
    
    def _apply_insert_operation(self, original_content: str, change_spec: Dict[str, Any]) -> str:
        """Apply an insert operation."""
        original_context = change_spec['original_context']
        modified_content = change_spec['modified_content']
        
        # Find the original context in the file content
        pos = original_content.find(original_context)
        if pos == -1:
            # Try fuzzy matching
            best_match = self._find_best_fuzzy_match(original_content, original_context)
            if best_match:
                start, end = best_match
                return original_content[:start] + original_context + modified_content + original_content[end:]
            return None
        
        # Insert the modified content after the original context
        insert_pos = pos + len(original_context)
        return original_content[:insert_pos] + modified_content + original_content[insert_pos:]
    
    def _apply_delete_operation(self, original_content: str, change_spec: Dict[str, Any]) -> str:
        """Apply a delete operation."""
        original_context = change_spec['original_context']
        
        # Find the original context in the file content
        pos = original_content.find(original_context)
        if pos == -1:
            # Try fuzzy matching
            best_match = self._find_best_fuzzy_match(original_content, original_context)
            if best_match:
                start, end = best_match
                return original_content[:start] + original_content[end:]
            return None
        
        # Remove the original context
        return original_content.replace(original_context, '', 1)
    
    def _apply_append_operation(self, original_content: str, change_spec: Dict[str, Any]) -> str:
        """Apply an append operation."""
        modified_content = change_spec['modified_content']
        
        # Simply append the content
        return original_content + '\n' + modified_content
    
    def _find_best_fuzzy_match(self, content: str, target: str) -> Tuple[int, int]:
        """Find the best fuzzy match for target in content."""
        if len(target) < 10:  # Require minimum length for meaningful matching
            return None
        
        # Split content into lines and look for best match
        lines = content.splitlines(keepends=True)
        
        # Try to find a block of lines that closely matches the target
        target_lines = target.splitlines(keepends=True)
        target_len = len(target_lines)
        
        best_ratio = 0
        best_match = None
        
        for i in range(len(lines) - target_len + 1):
            # Reconstruct a block of the same size as target
            block = ''.join(lines[i:i + target_len])
            ratio = difflib.SequenceMatcher(None, target, block).ratio()
            
            if ratio > best_ratio and ratio > 0.8:  # Require at least 80% similarity
                best_ratio = ratio
                best_match = (sum(len(l) for l in lines[:i]), sum(len(l) for l in lines[:i + target_len]))
        
        return best_match
    
    def _validate_change(self, new_content: str, file_path: str) -> Dict[str, Any]:
        """Validate the changed content."""
        # 1. Check for dangerous patterns
        dangerous_patterns = [
            r'exec\s*\(',
            r'eval\s*\(',
            r'os\.system\s*\(',
            r'subprocess\.call\s*\(',
            r'subprocess\.run\s*\([^,]*?,\s*shell\s*=\s*True',
            r'input\s*\(\s*\)\s*in\s*\[\s*"rm"\s*,\s*"del"\s*]'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, new_content, re.IGNORECASE):
                return {
                    'valid': False,
                    'error_code': 'dangerous_pattern',
                    'details': f'Dangerous pattern detected: {pattern}'
                }
        
        # 2. AST parse the modified content (for Python files)
        if file_path.endswith('.py'):
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return {
                    'valid': False,
                    'error_code': 'syntax_error',
                    'details': f'Syntax error in modified content: {str(e)}'
                }
        
        # 3. Compile check (for Python files)
        if file_path.endswith('.py'):
            # Write to a temporary file for compilation check
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(new_content)
                temp_path = temp_file.name
            
            try:
                compile_result = py_compile.compile(temp_path, doraise=True)
            except py_compile.PyCompileError as e:
                os.unlink(temp_path)
                return {
                    'valid': False,
                    'error_code': 'compile_error',
                    'details': f'Compilation error: {str(e)}'
                }
            
            os.unlink(temp_path)
        
        # 4. Lint check (if enabled)
        if self.enable_linter and file_path.endswith('.py'):
            lint_result = self._run_lint_check(new_content)
            if not lint_result['valid']:
                return lint_result
        
        return {'valid': True}
    
    def _run_lint_check(self, content: str) -> Dict[str, Any]:
        """Run linting on the content."""
        # For simplicity, we'll just write to a temp file and run flake8 on it
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Run flake8 on the temp file if available
            result = subprocess.run(
                ['flake8', temp_path, '--max-line-length=120'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # For now, just warn about lint errors but don't fail
                print(f"Lint warnings (not failing): {result.stdout}{result.stderr}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # If flake8 is not installed or times out, skip the lint check
            pass
        finally:
            os.unlink(temp_path)
        
        return {'valid': True}
    
    def _create_snapshot(self, file_path: str, task_id: str) -> str:
        """Create a snapshot of the file before modification."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        relative_path = Path(file_path).relative_to('/workspace/plka')
        snapshot_subdir = self.snapshots_dir / relative_path.parent
        snapshot_subdir.mkdir(parents=True, exist_ok=True)
        
        snapshot_filename = f"{relative_path.name}.{timestamp}.{task_id[:8]}.bak"
        snapshot_path = snapshot_subdir / snapshot_filename
        
        # Copy the current file to the snapshot location
        shutil.copy2(file_path, snapshot_path)
        
        return str(snapshot_path)
    
    def _restore_from_snapshot(self, snapshot_path: str, file_path: str):
        """Restore a file from a snapshot."""
        if Path(snapshot_path).exists():
            shutil.copy2(snapshot_path, file_path)


# Example usage:
if __name__ == "__main__":
    editor = FileEditor()
    
    # Example change specification
    change_spec = {
        'file_path': '/workspace/plka/projects/example/main.py',
        'operation': 'append',
        'original_context': '',
        'modified_content': '# Hello function added by PLKA\n\ndef hello():\n    print("Hello from PLKA!")\n',
        'task_id': 'TASK-EXAMPLE-001'
    }
    
    # Create the example directory and file if they don't exist
    example_dir = Path('/workspace/plka/projects/example')
    example_dir.mkdir(exist_ok=True)
    main_py = example_dir / 'main.py'
    if not main_py.exists():
        main_py.write_text('# Example main.py file\n\n')
    
    result = editor.apply_change(change_spec)
    print("Change result:", result)