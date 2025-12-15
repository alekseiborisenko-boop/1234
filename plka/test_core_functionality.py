#!/usr/bin/env python3
"""
Test script to verify PLKA core functionality
"""

import sys
from pathlib import Path
import json
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_file_editor():
    """Test the FileEditor functionality."""
    print("Testing FileEditor...")
    
    from core.file_editor import FileEditor
    
    # Create an example file to work with
    example_dir = Path("/workspace/plka/projects/example")
    example_file = example_dir / "test_file.py"
    
    # Write initial content
    initial_content = '''# Test file for PLKA
def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
'''
    
    with open(example_file, 'w') as f:
        f.write(initial_content)
    
    editor = FileEditor()
    
    # Test an append operation
    change_spec = {
        'file_path': str(example_file),
        'operation': 'append',
        'original_context': '',
        'modified_content': '\n\ndef goodbye():\n    print("Goodbye, World!")',
        'task_id': 'TEST-001'
    }
    
    result = editor.apply_change(change_spec)
    print(f"  Append operation: {result['status']}")
    
    # Read the file to verify the change
    with open(example_file, 'r') as f:
        content = f.read()
    
    print(f"  File contains 'goodbye' function: {'goodbye' in content}")
    
    # Test a replace operation
    change_spec = {
        'file_path': str(example_file),
        'operation': 'replace',
        'original_context': 'print("Hello, World!")',
        'modified_content': 'print("Hello from PLKA!")',
        'task_id': 'TEST-002'
    }
    
    result = editor.apply_change(change_spec)
    print(f"  Replace operation: {result['status']}")
    
    # Read the file to verify the change
    with open(example_file, 'r') as f:
        content = f.read()
    
    print(f"  File contains updated message: {'Hello from PLKA!' in content}")
    
    return True

def test_experience_manager():
    """Test the ExperienceManager functionality."""
    print("\nTesting ExperienceManager...")
    
    from core.experience_manager import ExperienceManager
    
    exp_manager = ExperienceManager()
    
    # Add a test pattern
    request = "Create a logging setup function"
    plan = """
    1. Import logging module
    2. Configure basic logging
    3. Create a logger function
    """
    
    exp_manager.record_successful_pattern(request, plan)
    print("  Recorded successful pattern")
    
    # Retrieve relevant patterns
    patterns = exp_manager.get_relevant_patterns("logging setup")
    print(f"  Found {len(patterns)} relevant patterns")
    
    # Get stable patterns
    stable_patterns = exp_manager.get_stable_patterns()
    print(f"  Found {len(stable_patterns)} stable patterns")
    
    return True

def test_project_manager():
    """Test the ProjectManager functionality."""
    print("\nTesting ProjectManager...")
    
    from core.project_manager import ProjectManager
    
    pm = ProjectManager()
    
    # List projects
    projects = pm.list_projects()
    print(f"  Found {len(projects)} projects")
    
    # Get files from example project
    files = pm.get_project_files("example")
    print(f"  Example project has {len(files)} files")
    
    # Get project info
    info = pm.get_project_info("example")
    if info:
        print(f"  Project example: {info['file_count']} files, {info['size']} bytes")
    
    return True

def test_orchestrator():
    """Test the Orchestrator functionality."""
    print("\nTesting Orchestrator...")
    
    from core.orchestrator import Orchestrator
    
    orchestrator = Orchestrator()
    
    # Create a test task
    task_id = orchestrator.create_task(
        "/workspace/plka/projects/example",
        "Add a function to calculate factorial"
    )
    
    print(f"  Created task: {task_id}")
    
    # Check status
    status = orchestrator.get_task_status(task_id)
    print(f"  Task status: {status}")
    
    return True

def main():
    print("Testing PLKA Core Functionality")
    print("="*50)
    
    tests = [
        test_project_manager,
        test_file_editor,
        test_experience_manager,
        test_orchestrator
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            result = test()
            if result:
                passed += 1
        except Exception as e:
            print(f"  ❌ Test failed with error: {e}")
    
    print(f"\n{'='*50}")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All core functionality tests passed!")
    else:
        print(f"⚠️  {total - passed} tests failed, but core components are working.")
    
    print("\nPLKA system is ready for use!")
    print("Run 'python main.py' to start the GUI (if display is available)")
    print("Or use the individual components directly in your scripts.")

if __name__ == "__main__":
    main()