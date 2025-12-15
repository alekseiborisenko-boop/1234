"""
ProjectManager component for PLKA
Handles project discovery, file scanning, and project-related operations
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class ProjectManager:
    def __init__(self, base_path: str = "/workspace/plka"):
        self.base_path = Path(base_path)
        self.projects_path = self.base_path / "projects"
        self.projects_path.mkdir(exist_ok=True)
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects in the projects directory."""
        projects = []
        
        for item in self.projects_path.iterdir():
            if item.is_dir():
                project_info = {
                    'name': item.name,
                    'path': str(item),
                    'created': datetime.fromtimestamp(item.stat().st_ctime).isoformat(),
                    'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                    'size': self._get_directory_size(item),
                    'files': self._count_files(item)
                }
                projects.append(project_info)
        
        return projects
    
    def _get_directory_size(self, path: Path) -> int:
        """Calculate the total size of a directory."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                try:
                    total_size += filepath.stat().st_size
                except OSError:
                    # Skip files that can't be accessed
                    continue
        return total_size
    
    def _count_files(self, path: Path) -> int:
        """Count the number of files in a directory."""
        count = 0
        for dirpath, dirnames, filenames in os.walk(path):
            # Skip common ignored directories
            dirnames[:] = [d for d in dirnames if not self._is_ignored_directory(d)]
            count += len(filenames)
        return count
    
    def _is_ignored_directory(self, dirname: str) -> bool:
        """Check if a directory should be ignored."""
        ignored_dirs = {'.git', '__pycache__', '.venv', '.idea', 'node_modules', '.vscode', 'dist', 'build'}
        return dirname in ignored_dirs
    
    def get_project_files(self, project_name: str) -> List[Dict[str, Any]]:
        """Get all files in a specific project."""
        project_path = self.projects_path / project_name
        
        if not project_path.exists():
            return []
        
        files = []
        for file_path in project_path.rglob("*"):
            if file_path.is_file() and not self._is_ignored_file(file_path):
                file_info = {
                    'name': file_path.name,
                    'path': str(file_path),
                    'relative_path': str(file_path.relative_to(project_path)),
                    'size': file_path.stat().st_size,
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    'extension': file_path.suffix
                }
                files.append(file_info)
        
        return sorted(files, key=lambda x: x['relative_path'])
    
    def _is_ignored_file(self, file_path: Path) -> bool:
        """Check if a file should be ignored."""
        # Check parent directories
        for parent in file_path.parents:
            if self._is_ignored_directory(parent.name):
                return True
        
        # Check file extension
        ignored_extensions = {'.pyc', '.pyo', '.exe', '.dll', '.so', '.o', '.obj'}
        if file_path.suffix in ignored_extensions:
            return True
        
        # Check specific file names
        ignored_files = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
        if file_path.name in ignored_files:
            return True
        
        return False
    
    def create_project(self, project_name: str, template: str = None) -> bool:
        """Create a new project with the given name."""
        project_path = self.projects_path / project_name
        
        if project_path.exists():
            return False  # Project already exists
        
        project_path.mkdir(exist_ok=True)
        
        # Create basic project structure
        (project_path / "src").mkdir(exist_ok=True)
        (project_path / "tests").mkdir(exist_ok=True)
        (project_path / "docs").mkdir(exist_ok=True)
        
        # Create a basic main file based on template or default
        if template == "python":
            main_content = '''#!/usr/bin/env python3
"""
Main module for {project_name}
"""

def main():
    """Main entry point for the application."""
    print("Hello from {project_name}!")


if __name__ == "__main__":
    main()
'''.format(project_name=project_name)
        else:
            # Default template
            main_content = f'# {project_name} main file\n\n'
        
        with open(project_path / "main.py", 'w', encoding='utf-8') as f:
            f.write(main_content)
        
        # Create a default build configuration
        build_config = {
            "entry_point": "main.py",
            "builder": "pyinstaller",
            "onefile": True,
            "console": True,
            "extra_args": []
        }
        
        with open(project_path / "agent_build.json", 'w') as f:
            json.dump(build_config, f, indent=2)
        
        return True
    
    def delete_project(self, project_name: str) -> bool:
        """Delete a project."""
        project_path = self.projects_path / project_name
        
        if not project_path.exists():
            return False
        
        import shutil
        shutil.rmtree(project_path)
        return True
    
    def get_project_info(self, project_name: str) -> Dict[str, Any]:
        """Get detailed information about a project."""
        project_path = self.projects_path / project_name
        
        if not project_path.exists():
            return {}
        
        # Count different file types
        file_types = {}
        for file_path in project_path.rglob("*"):
            if file_path.is_file() and not self._is_ignored_file(file_path):
                ext = file_path.suffix.lower()
                file_types[ext] = file_types.get(ext, 0) + 1
        
        project_info = {
            'name': project_name,
            'path': str(project_path),
            'created': datetime.fromtimestamp(project_path.stat().st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(project_path.stat().st_mtime).isoformat(),
            'size': self._get_directory_size(project_path),
            'file_count': self._count_files(project_path),
            'file_types': file_types
        }
        
        return project_info


# Example usage:
if __name__ == "__main__":
    pm = ProjectManager()
    
    # List existing projects
    projects = pm.list_projects()
    print(f"Found {len(projects)} projects:")
    for proj in projects:
        print(f"  - {proj['name']} ({proj['files']} files, {proj['size']} bytes)")
    
    # Create a new example project if it doesn't exist
    example_project = "example_project"
    if not any(p['name'] == example_project for p in projects):
        success = pm.create_project(example_project, "python")
        if success:
            print(f"Created project: {example_project}")
    
    # Get files from the example project
    files = pm.get_project_files(example_project)
    print(f"\nFiles in {example_project}:")
    for f in files[:10]:  # Show first 10 files
        print(f"  - {f['relative_path']} ({f['size']} bytes)")
    
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more files")