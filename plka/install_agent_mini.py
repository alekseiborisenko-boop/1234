#!/usr/bin/env python3
"""
Installer for PLKA (Practical Local Code Assistant) v2.0
Creates the directory structure and initializes all components
"""

import os
import sys
import json
import shutil
import subprocess
import platform
from pathlib import Path


def detect_hardware():
    """Detect hardware capabilities to recommend appropriate models."""
    try:
        import psutil
        cpu_cores = psutil.cpu_count()
        # Get RAM in GB, handling the case where virtual_memory() might not be available
        try:
            ram_gb = psutil.virtual_memory().total // (1024**3)
        except:
            ram_gb = 8  # Default fallback
        
        print(f"Detected: {cpu_cores} cores, {ram_gb}GB RAM", end="")
        
        # Check for NVIDIA GPU
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                gpu_vram = int(result.stdout.strip().split('\n')[0])  # Take first GPU
                print(f", GPU with {gpu_vram}MB VRAM")
                if gpu_vram >= 12 * 1024:  # 12GB+
                    print("  → Hardware class: gpu_12gb+")
                    return "gpu_12gb+"
            else:
                print(", no compatible GPU")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError, FileNotFoundError):
            print(", no compatible GPU")
        
        # Fallback to CPU-based classification
        if ram_gb >= 32 and cpu_cores >= 8:
            print("  → Hardware class: cpu_high")
            return "cpu_high"
        elif ram_gb >= 16:
            print("  → Hardware class: cpu_medium")
            return "cpu_medium"
        else:
            print("  → Hardware class: cpu_low")
            return "cpu_low"
    except ImportError:
        print("  → Hardware detection failed (psutil not available)")
        return "cpu_medium"


def create_directory_structure(base_path):
    """Create the required directory structure."""
    directories = [
        base_path / "projects",
        base_path / "chromadb", 
        base_path / "config",
        base_path / "snapshots",
        base_path / "dist",
        base_path / "backups",
        base_path / "logs",
        base_path / "projects" / "example",
        base_path / "ui",
        base_path / "core"
    ]
    
    print("Creating directory structure...")
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {directory.relative_to(base_path)}")


def initialize_databases(base_path):
    """Initialize the SQLite databases."""
    import sqlite3
    from datetime import datetime
    
    print("Initializing databases...")
    
    # Chat history database
    chat_db_path = base_path / "chat_history.db"
    conn = sqlite3.connect(chat_db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY,
            project_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY,
            session_id INTEGER,
            role TEXT CHECK(role IN ('user', 'agent')),
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            task_id TEXT,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"  ✅ {chat_db_path.name}")
    
    # Agent memory database
    agent_db_path = base_path / "agent_memory.db"
    conn = sqlite3.connect(agent_db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            project TEXT,
            task_id TEXT,
            step TEXT,
            component TEXT,
            action_type TEXT,
            status TEXT CHECK(status IN ('SUCCESS','ERROR','SKIPPED')),
            details_json TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"  ✅ {agent_db_path.name}")
    
    # Agent knowledge database
    knowledge_db_path = base_path / "agent_knowledge.db"
    conn = sqlite3.connect(knowledge_db_path)
    cursor = conn.cursor()
    
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
    print(f"  ✅ {knowledge_db_path.name}")


def generate_llm_config(base_path, hardware_class):
    """Generate the LLM profiles configuration."""
    print("Generating LLM configuration...")
    
    model_profiles = {
        "cpu_low": {
            "planner": "phi3-mini-q5.gguf",
            "coder": "qwen2.5-coder-7b-q4.gguf"
        },
        "cpu_medium": {
            "planner": "phi3-mini-q5.gguf", 
            "coder": "qwen2.5-coder-14b-q4.gguf"
        },
        "cpu_high": {
            "planner": "deepseek-r1-7b-q4.gguf",
            "coder": "qwen2.5-coder-14b-q5.gguf"
        },
        "gpu_12gb+": {
            "planner": "deepseek-r1-14b-q4.gguf",
            "coder": "qwen2.5-coder-32b-q4.gguf"
        }
    }
    
    profiles = model_profiles.get(hardware_class, model_profiles["cpu_medium"])
    
    config = {
        "hardware_class": hardware_class,
        "koboldcpp_url": "http://localhost:5001",
        "profiles": {
            "planner": {
                "local": profiles["planner"],
                "cloud": "gpt-4o-mini"
            },
            "coder": {
                "local": profiles["coder"], 
                "cloud": "gpt-4o"
            }
        }
    }
    
    config_path = base_path / "config" / "llm_profiles.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"  ✅ {config_path.name}")


def create_example_project(base_path):
    """Create an example project for testing."""
    print("Creating example project...")
    
    example_path = base_path / "projects" / "example"
    
    # Create main.py
    main_content = '''#!/usr/bin/env python3
"""
Example project for PLKA
This is a simple calculator application to demonstrate PLKA capabilities
"""

def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    return a - b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def divide(a, b):
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def main():
    """Main entry point."""
    print("Simple Calculator Example")
    print("Operations: add, subtract, multiply, divide")
    
    # Example usage
    result = add(5, 3)
    print(f"5 + 3 = {result}")


if __name__ == "__main__":
    main()
'''
    
    main_path = example_path / "main.py"
    with open(main_path, 'w', encoding='utf-8') as f:
        f.write(main_content)
    
    # Create a basic build configuration
    build_config = {
        "entry_point": "main.py",
        "builder": "pyinstaller",
        "onefile": True,
        "console": True,
        "extra_args": []
    }
    
    build_config_path = example_path / "agent_build.json"
    with open(build_config_path, 'w') as f:
        json.dump(build_config, f, indent=2)
    
    print(f"  ✅ {main_path.name}")
    print(f"  ✅ {build_config_path.name}")


def check_dependencies():
    """Check if required dependencies are available."""
    print("Checking dependencies...")
    
    required_packages = [
        ("PyQt6", "PyQt6"),
        ("chromadb", "chromadb"), 
        ("sentence-transformers", "sentence_transformers"),
        ("torch", "torch"),
        ("pyinstaller", "PyInstaller")
    ]
    
    missing_packages = []
    
    for display_name, import_name in required_packages:
        try:
            __import__(import_name.replace('-', '_'))
            print(f"  ✅ {display_name}")
        except ImportError:
            print(f"  ❌ {display_name} (will need to install)")
            missing_packages.append(display_name.lower().replace(" ", "-"))
    
    if missing_packages:
        print(f"\nInstalling missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            print("  ✅ Dependencies installed successfully")
        except subprocess.CalledProcessError:
            print("  ⚠️  Could not install some dependencies. Please install manually.")
    
    # Check for psutil (for hardware detection)
    try:
        import psutil
        print("  ✅ psutil")
    except ImportError:
        print("  ❌ psutil (installing...)")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
            print("  ✅ psutil installed")
        except subprocess.CalledProcessError:
            print("  ⚠️  Could not install psutil. Hardware detection may not work.")


def main():
    """Main installation function."""
    print("PLKA (Practical Local Code Assistant) v2.0 Installer")
    print("=" * 55)
    
    # Use the current directory as base path
    base_path = Path("/workspace/plka").resolve()
    print(f"Installing to: {base_path}")
    print()
    
    # Step 1: Detect hardware
    print("[1/8] Detecting hardware capabilities...")
    hardware_class = detect_hardware()
    print()
    
    # Step 2: Create directory structure
    print("[2/8] Creating directory structure...")
    create_directory_structure(base_path)
    print()
    
    # Step 3: Initialize databases
    print("[3/8] Initializing databases...")
    initialize_databases(base_path)
    print()
    
    # Step 4: Generate LLM config
    print("[4/8] Generating LLM configuration...")
    generate_llm_config(base_path, hardware_class)
    print()
    
    # Step 5: Check dependencies
    print("[5/8] Checking and installing dependencies...")
    check_dependencies()
    print()
    
    # Step 6: Create example project
    print("[6/8] Creating example project...")
    create_example_project(base_path)
    print()
    
    # Step 7: Initialize RAG for example project
    print("[7/8] Initializing RAG index for example project...")
    try:
        # Import and index the example project
        from core.rag_service import RAGService
        rag_service = RAGService()
        rag_service.index_project(base_path / "projects" / "example")
        print("  ✅ Example project indexed")
    except Exception as e:
        print(f"  ⚠️  Could not initialize RAG: {e}")
    print()
    
    # Step 8: Complete installation
    print("[8/8] Installation complete!")
    print()
    print("PLKA has been successfully installed!")
    print()
    print("To start PLKA, run:")
    print(f"  cd {base_path}")
    print("  python main.py")
    print()
    print("Directory structure created:")
    print(f"  {base_path}/")
    print("  ├── projects/          # Your projects")
    print("  ├── chromadb/          # RAG vector database") 
    print("  ├── config/            # Configuration files")
    print("  ├── snapshots/         # File change snapshots")
    print("  ├── dist/              # Built executables")
    print("  ├── backups/           # Database backups")
    print("  └── logs/              # Application logs")
    print()
    print("The example project is available in projects/example/")
    print("Try asking PLKA to modify or extend the calculator functions!")


if __name__ == "__main__":
    main()