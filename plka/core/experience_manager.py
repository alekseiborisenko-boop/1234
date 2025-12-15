"""
ExperienceManager component for PLKA
Implements "second head" functionality by learning from past successful patterns
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import re


class ExperienceManager:
    def __init__(self, db_path: str = "/workspace/plka/agent_knowledge.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the knowledge database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create the items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                type TEXT,
                name TEXT UNIQUE,
                content TEXT,
                tags TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                last_used_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_successful_pattern(self, request: str, plan: str):
        """Record a successful pattern from a completed task."""
        # Extract potential patterns from the request and plan
        patterns = self._extract_patterns(request, plan)
        
        for pattern in patterns:
            self._upsert_pattern(pattern)
    
    def _extract_patterns(self, request: str, plan: str) -> List[Dict[str, Any]]:
        """Extract potential patterns from a request and plan."""
        patterns = []
        
        # Look for common patterns in the plan
        # For example, if the plan involves creating a function, we might extract a function template
        if 'create a function' in request.lower() or 'add function' in request.lower():
            # Extract function definition from plan
            function_matches = re.findall(r'def\s+(\w+)\s*\([^)]*\):[^#]*?(?=\n\w|$)', plan, re.MULTILINE | re.DOTALL)
            for func_name in function_matches:
                patterns.append({
                    'type': 'function_template',
                    'name': f'function_{func_name}',
                    'content': self._extract_function_content(plan, func_name),
                    'tags': json.dumps(['function', 'template'])
                })
        
        # Look for import patterns
        if 'import' in plan.lower():
            import_matches = re.findall(r'(import\s+\w+|from\s+\w+\s+import\s+[\w\s,]+)', plan)
            if import_matches:
                patterns.append({
                    'type': 'import_pattern',
                    'name': f'import_pattern_{len(import_matches)}',
                    'content': '\n'.join(import_matches),
                    'tags': json.dumps(['import', 'setup'])
                })
        
        # Look for common code patterns
        if 'logging' in request.lower() or 'log' in request.lower():
            logging_pattern = self._extract_logging_pattern(plan)
            if logging_pattern:
                patterns.append({
                    'type': 'logging_setup',
                    'name': 'logging_setup',
                    'content': logging_pattern,
                    'tags': json.dumps(['logging', 'setup'])
                })
        
        # Add the complete plan as a pattern if it's significant
        if len(plan) > 50:  # Only if it's a substantial plan
            request_keywords = self._extract_keywords(request)
            pattern_name = f"{'_'.join(request_keywords[:3])}_pattern" if request_keywords else "general_pattern"
            
            patterns.append({
                'type': 'general_pattern',
                'name': pattern_name,
                'content': plan,
                'tags': json.dumps(request_keywords + ['general'])
            })
        
        return patterns
    
    def _extract_function_content(self, plan: str, func_name: str) -> str:
        """Extract the content of a specific function from a plan."""
        # Look for the function definition in the plan
        pattern = rf'def\s+{func_name}\s*\([^)]*\):[^#]*?(?=\n\w+\s+=|\n\w+\s+def|\n\w+\s+class|\Z)'
        matches = re.findall(pattern, plan, re.MULTILINE | re.DOTALL)
        return matches[0] if matches else f"def {func_name}():\n    pass"
    
    def _extract_logging_pattern(self, plan: str) -> Optional[str]:
        """Extract logging setup pattern from a plan."""
        # Look for logging-related code
        logging_matches = re.findall(r'import logging.*?^.*?(?=def |class |\Z)', plan, re.MULTILINE | re.DOTALL)
        return logging_matches[0] if logging_matches else None
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction - in practice this could be more sophisticated
        words = re.findall(r'\b\w{4,}\b', text.lower())
        return list(set(words))  # Return unique keywords
    
    def _upsert_pattern(self, pattern: Dict[str, Any]):
        """Insert or update a pattern in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO items (type, name, content, tags, success_count, fail_count, last_used_at)
                VALUES (?, ?, ?, ?, 1, 0, ?)
                ON CONFLICT(name) DO UPDATE SET
                    success_count = success_count + 1,
                    last_used_at = excluded.last_used_at
            ''', (
                pattern['type'],
                pattern['name'],
                pattern['content'],
                pattern['tags'],
                datetime.now().isoformat()
            ))
            
            conn.commit()
        except sqlite3.IntegrityError:
            # If there's a conflict, just update the success count
            cursor.execute('''
                UPDATE items
                SET success_count = success_count + 1,
                    last_used_at = ?
                WHERE name = ?
            ''', (datetime.now().isoformat(), pattern['name']))
            
            conn.commit()
        
        conn.close()
    
    def get_relevant_patterns(self, request: str) -> List[Dict[str, Any]]:
        """Get relevant patterns based on the request."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract keywords from the request
        keywords = self._extract_keywords(request)
        
        if not keywords:
            # If no keywords, return top patterns by success count
            cursor.execute('''
                SELECT type, name, content, tags, success_count, fail_count
                FROM items
                WHERE success_count >= 3
                ORDER BY success_count DESC
                LIMIT 5
            ''')
        else:
            # Build a query to find patterns matching keywords
            keyword_placeholders = ','.join(['?' for _ in keywords])
            query = f'''
                SELECT type, name, content, tags, success_count, fail_count
                FROM items
                WHERE success_count >= 3
                AND (content LIKE ? OR tags LIKE ?)
                ORDER BY success_count DESC
                LIMIT 5
            '''
            
            # Search for each keyword
            all_results = []
            for keyword in keywords:
                cursor.execute(query, (f'%{keyword}%', f'%{keyword}%'))
                all_results.extend(cursor.fetchall())
            
            # Remove duplicates while preserving order
            seen = set()
            unique_results = []
            for result in all_results:
                name = result[1]
                if name not in seen:
                    seen.add(name)
                    unique_results.append(result)
            
            # Limit to 5 results
            results = unique_results[:5]
        
        conn.close()
        
        # Format results
        patterns = []
        for row in (results if 'results' in locals() else cursor.fetchall()):
            try:
                tags = json.loads(row[3]) if row[3] else []
            except json.JSONDecodeError:
                tags = []
            
            patterns.append({
                'type': row[0],
                'name': row[1],
                'content': row[2],
                'tags': tags,
                'success_count': row[4],
                'fail_count': row[5]
            })
        
        return patterns
    
    def record_failed_attempt(self, request: str, plan: str):
        """Record a failed attempt to learn from mistakes."""
        # For now, we'll just log this - in a more advanced system,
        # we might analyze why it failed and update patterns accordingly
        pass
    
    def get_stable_patterns(self) -> List[Dict[str, Any]]:
        """Get patterns that have been successful multiple times."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT type, name, content, tags, success_count, fail_count
            FROM items
            WHERE success_count >= 3
            ORDER BY success_count DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        patterns = []
        for row in results:
            try:
                tags = json.loads(row[3]) if row[3] else []
            except json.JSONDecodeError:
                tags = []
            
            patterns.append({
                'type': row[0],
                'name': row[1],
                'content': row[2],
                'tags': tags,
                'success_count': row[4],
                'fail_count': row[5]
            })
        
        return patterns


# Example usage:
if __name__ == "__main__":
    exp_manager = ExperienceManager()
    
    # Example: Record a successful pattern
    request = "Add a logging setup to the main function"
    plan = """
    1. Import logging module
    2. Configure logging with appropriate level and format
    3. Add logger instance
    4. Use logger in the main function
    """
    
    exp_manager.record_successful_pattern(request, plan)
    print("Recorded successful pattern")
    
    # Example: Get relevant patterns for a new request
    new_request = "I need to add logging to my application"
    relevant_patterns = exp_manager.get_relevant_patterns(new_request)
    print(f"Found {len(relevant_patterns)} relevant patterns")
    
    for pattern in relevant_patterns:
        print(f"- {pattern['name']}: {pattern['content'][:100]}...")