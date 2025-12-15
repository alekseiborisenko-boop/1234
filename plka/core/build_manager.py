"""
BuildManager component for PLKA
Handles building portable EXE files using PyInstaller
"""

import os
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class CommandExecutor:
    """Secure command executor with whitelisting."""
    
    def __init__(self, config_path: str = "/workspace/plka/config/security.json"):
        self.config_path = config_path
        self.whitelist = self._load_whitelist()
    
    def _load_whitelist(self) -> Dict[str, list]:
        """Load the command whitelist from config."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            return config.get('allowed_commands', {})
        except FileNotFoundError:
            # Default whitelist if config doesn't exist
            return {
                "pyinstaller": ["--onefile", "--noconsole", "--add-data", "--add-binary", "--hidden-import"],
                "python": ["-m", "py_compile"],
                "pytest": [],
                "pycodestyle": [],
                "flake8": []
            }
    
    def execute_command(self, cmd: list) -> Dict[str, Any]:
        """Execute a command if it's in the whitelist."""
        if not cmd:
            return {'status': 'error', 'message': 'Empty command'}
        
        command_name = cmd[0]
        
        if command_name not in self.whitelist:
            return {'status': 'error', 'message': f'Command not whitelisted: {command_name}'}
        
        allowed_args = self.whitelist[command_name]
        
        # Check if all arguments are allowed (if specific args are restricted)
        if allowed_args and allowed_args != ["-m", "py_compile"]:  # Special case for python -m py_compile
            for arg in cmd[1:]:
                if arg not in allowed_args and not any(allowed_arg in arg for allowed_arg in allowed_args):
                    return {'status': 'error', 'message': f'Argument not allowed: {arg} for command {command_name}'}
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            return {
                'status': 'success' if result.returncode == 0 else 'error',
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        except subprocess.TimeoutExpired:
            return {'status': 'error', 'message': 'Command timed out'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


class BuildManager:
    def __init__(self, base_path: str = "/workspace/plka"):
        self.base_path = Path(base_path)
        self.dist_path = self.base_path / "dist"
        self.dist_path.mkdir(exist_ok=True)
        self.command_executor = CommandExecutor()
    
    def build_project(self, project_path: str) -> Dict[str, Any]:
        """Build an EXE from a project."""
        project_path = Path(project_path)
        
        # Find the build configuration
        build_config_path = project_path / "agent_build.json"
        if build_config_path.exists():
            with open(build_config_path, 'r') as f:
                build_config = json.load(f)
        else:
            # Use default configuration
            build_config = {
                "entry_point": "main.py",
                "builder": "pyinstaller",
                "onefile": True,
                "console": False,
                "extra_args": []
            }
        
        entry_point = project_path / build_config["entry_point"]
        
        if not entry_point.exists():
            return {
                'status': 'error',
                'message': f'Entry point does not exist: {entry_point}'
            }
        
        # Prepare build command based on the builder specified
        if build_config["builder"] == "pyinstaller":
            result = self._build_with_pyinstaller(
                entry_point,
                build_config,
                project_path
            )
        else:
            return {
                'status': 'error',
                'message': f'Unsupported builder: {build_config["builder"]}'
            }
        
        return result
    
    def _build_with_pyinstaller(self, entry_point: Path, build_config: Dict[str, Any], project_path: Path) -> Dict[str, Any]:
        """Build using PyInstaller."""
        # Prepare the PyInstaller command
        cmd = ["pyinstaller"]
        
        if build_config.get("onefile", True):
            cmd.append("--onefile")
        
        if not build_config.get("console", True):
            cmd.append("--noconsole")
        
        # Add any extra arguments from the config
        extra_args = build_config.get("extra_args", [])
        cmd.extend(extra_args)
        
        # Add the entry point
        cmd.append(str(entry_point))
        
        # Create a temporary build directory specific to this project
        build_dir = self.dist_path / f"{project_path.name}_build_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        build_dir.mkdir(exist_ok=True)
        
        # Change to the project directory for the build
        original_cwd = Path.cwd()
        
        try:
            os.chdir(project_path)
            
            # Execute the build command
            result = self.command_executor.execute_command(cmd)
            
            if result['status'] == 'success':
                # Find the built executable
                dist_dir = project_path / "dist"
                exe_files = list(dist_dir.glob("*.exe")) + list(dist_dir.glob("*"))  # Also check for non-.exe files on other OS
                
                if exe_files:
                    # Move the executable to our main dist directory
                    output_exe = exe_files[0]
                    final_path = self.dist_path / f"{project_path.name}_{output_exe.name}"
                    shutil.move(str(output_exe), str(final_path))
                    
                    # Clean up build artifacts
                    build_artifacts = project_path / "build"
                    if build_artifacts.exists():
                        shutil.rmtree(build_artifacts)
                    
                    if dist_dir.exists():
                        shutil.rmtree(dist_dir)
                    
                    return {
                        'status': 'success',
                        'message': f'Build completed successfully. Executable at: {final_path}',
                        'executable_path': str(final_path)
                    }
                else:
                    return {
                        'status': 'error',
                        'message': 'Build completed but no executable found',
                        'stdout': result.get('stdout', ''),
                        'stderr': result.get('stderr', '')
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'Build failed: {result.get("message", "Unknown error")}',
                    'stdout': result.get('stdout', ''),
                    'stderr': result.get('stderr', '')
                }
        finally:
            # Restore the original working directory
            os.chdir(original_cwd)
    
    def create_default_build_config(self, project_path: str, entry_point: str = "main.py"):
        """Create a default build configuration for a project."""
        project_path = Path(project_path)
        config_path = project_path / "agent_build.json"
        
        default_config = {
            "entry_point": entry_point,
            "builder": "pyinstaller",
            "onefile": True,
            "console": False,
            "extra_args": []
        }
        
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)


# Example usage:
if __name__ == "__main__":
    build_manager = BuildManager()
    
    # Example: Create a default build config for the example project
    example_project = "/workspace/plka/projects/example"
    build_manager.create_default_build_config(example_project, "main.py")
    print(f"Created default build config for {example_project}")
    
    # Example: Build the example project (this would require PyInstaller to be installed)
    # result = build_manager.build_project(example_project)
    # print("Build result:", result)