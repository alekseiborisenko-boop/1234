# PLKA (Practical Local Code Assistant) v2.0

PLKA is a local AI assistant for Python project development, editing, testing, and building with a chat interface, advanced RAG, hardware-optimized models, and complete isolation.

## Features

- **Chat Interface**: Interactive chat instead of task fields
- **Advanced RAG**: HNSW indexing with quantization and optional reranking
- **Hardware Optimization**: Automatic model selection based on your hardware
- **Safe File Editing**: AST validation, syntax checking, and safety measures
- **Portable Builds**: PyInstaller EXE building with configuration
- **Experience Manager**: "Second head" learning from successful patterns
- **Complete Isolation**: Strict path validation and command whitelisting

## Architecture

```
Orchestrator (FSM) ←→ ChatInterface ←→ UI (PyQt6)
         ↓
   ┌─────────────┐
   │ RAGService  │ ← ChromaDB (HNSW+quantization)
   │ (Embed/RAG) │
   └──────┬──────┘
          ↓
ExperienceManager ← agent_knowledge.db
FileEditor ←→ BuildManager ←→ CommandExecutor
          ↓
     PathValidator (workspace/plka only)
```

## Components

- **ProjectManager**: Project discovery and file scanning
- **ChatInterface**: Chat UI with slash commands
- **Orchestrator**: FSM task management (PENDING→PLANNING→EDITING→VERIFYING→DONE/FAILED)
- **FileEditor**: Precise editing with AST validation and safety checks
- **RAGService**: Advanced embedding and retrieval
- **LLMClient**: KoboldCpp integration with hardware-optimized models
- **PathValidator**: Strict path validation
- **CommandExecutor**: Secure command execution with whitelisting
- **ExperienceManager**: Pattern learning from successful tasks
- **BuildManager**: PyInstaller EXE building

## Installation

Run the installer to set up PLKA:

```bash
cd /workspace/plka
python install_agent_mini.py
```

The installer will:
1. Detect your hardware and recommend appropriate models
2. Create the directory structure
3. Initialize SQLite databases
4. Generate LLM configuration
5. Verify dependencies and install missing ones
6. Create an example project
7. Initialize RAG index for the example project

## Usage

After installation, start PLKA:

```bash
cd /workspace/plka
python main.py
```

## Project Structure

```
/workspace/plka/
├── projects/                 # User projects
│   ├── example/              # Example project
│   └── ...
├── chromadb/                 # RAG vector database
├── config/                   # Configuration files
│   ├── llm_profiles.json     # Hardware-adapted model profiles
│   ├── rag.json              # RAG parameters
│   ├── security.json         # Security whitelist
│   └── prompts.yaml          # AI prompts
├── snapshots/                # File change snapshots
├── dist/                     # Built executables
├── backups/                  # Database backups
└── logs/                     # Application logs
```

## Slash Commands

In the chat interface, you can use these slash commands:
- `/index` - Index current project
- `/allindex` - Index all projects
- `/build` - Build EXE for current project
- `/test` - Test current file syntax
- `/clear` - Clear chat
- `/help` - Show help

## Safety Features

- **Path Validation**: Only allows operations within `/workspace/plka/`
- **Command Whitelisting**: Only allows safe commands like `pyinstaller`, `pytest`, etc.
- **Code Validation**: AST parsing, syntax checking, and linting
- **File Snapshots**: Automatic backup before changes
- **Dangerous Pattern Detection**: Blocks `eval`, `exec`, `os.system`, etc.

## Hardware Detection

PLKA automatically detects your hardware and recommends appropriate models:

- **cpu_low**: 4-16GB RAM, basic models
- **cpu_medium**: 16GB+ RAM, 8+ cores - recommended setup
- **cpu_high**: 32GB+ RAM, 8+ cores - high-performance models
- **gpu_12gb+**: 12GB+ VRAM GPU - maximum performance

## License

MIT License - see the LICENSE file for details.