"""
Main Window for PLKA (Practical Local Code Assistant)
Implements the UI layout described in the technical specification
"""

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QTextEdit, QLineEdit, QPushButton,
    QFrame, QTabWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor
import sqlite3


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLKA (Practical Local Code Assistant) v2.0")
        self.setGeometry(100, 100, 1400, 900)
        
        # Initialize core components
        self.current_project = None
        self.chat_history_db = "/workspace/plka/chat_history.db"
        self.init_databases()
        
        # Create the main UI
        self.init_ui()
        
        # Load projects
        self.load_projects()
    
    def init_databases(self):
        """Initialize SQLite databases as per specification."""
        # Chat history database
        conn = sqlite3.connect(self.chat_history_db)
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
        
        # Agent memory database
        agent_memory_db = "/workspace/plka/agent_memory.db"
        conn = sqlite3.connect(agent_memory_db)
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
        
        # Agent knowledge database
        knowledge_db = "/workspace/plka/agent_knowledge.db"
        conn = sqlite3.connect(knowledge_db)
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
    
    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel - Projects
        left_panel = self.create_left_panel()
        
        # Center panel - Chat
        center_panel = self.create_chat_panel()
        
        # Right panel - Task log
        right_panel = self.create_right_panel()
        
        # Create splitter for panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 800, 300])  # Set initial sizes
        
        main_layout.addWidget(splitter)
        
        # Set stylesheet for better appearance
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
    
    def create_left_panel(self):
        """Create the left panel with projects and controls."""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        # Projects label
        projects_label = QLabel("📁 Projects:")
        projects_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(projects_label)
        
        # Projects list
        self.projects_list = QListWidget()
        self.projects_list.itemClicked.connect(self.on_project_selected)
        layout.addWidget(self.projects_list)
        
        # Control buttons
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_projects)
        layout.addWidget(refresh_btn)
        
        index_current_btn = QPushButton("📚 Index Current")
        index_current_btn.clicked.connect(self.index_current_project)
        layout.addWidget(index_current_btn)
        
        index_all_btn = QPushButton("📚 Index All")
        index_all_btn.clicked.connect(self.index_all_projects)
        layout.addWidget(index_all_btn)
        
        build_exe_btn = QPushButton("⚙️ Build EXE")
        build_exe_btn.clicked.connect(self.build_current_project)
        layout.addWidget(build_exe_btn)
        
        layout.addStretch()  # Push buttons to top
        
        return frame
    
    def create_chat_panel(self):
        """Create the center chat panel."""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        # Chat history display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Consolas", 10))
        layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Enter your message or /command...")
        self.user_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.user_input)
        
        send_btn = QPushButton("➤ Send")
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)
        
        layout.addLayout(input_layout)
        
        return frame
    
    def create_right_panel(self):
        """Create the right panel with task log."""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        # Task log label
        task_label = QLabel("📋 Task Log")
        task_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(task_label)
        
        # Task list
        self.task_list = QListWidget()
        layout.addWidget(self.task_list)
        
        # Filter input
        filter_input = QLineEdit()
        filter_input.setPlaceholderText("🔍 Filter tasks...")
        layout.addWidget(filter_input)
        
        layout.addStretch()
        
        return frame
    
    def load_projects(self):
        """Load projects from the projects directory."""
        self.projects_list.clear()
        projects_dir = Path("/workspace/plka/projects")
        
        if projects_dir.exists():
            for item in projects_dir.iterdir():
                if item.is_dir():
                    project_item = QListWidgetItem(f"• {item.name}")
                    project_item.setData(Qt.ItemDataRole.UserRole, str(item))
                    self.projects_list.addItem(project_item)
    
    def on_project_selected(self, item):
        """Handle project selection."""
        project_path = item.data(Qt.ItemDataRole.UserRole)
        self.current_project = project_path
        self.load_chat_history_for_project()
        
        # Update UI to show project selected
        for i in range(self.projects_list.count()):
            current_item = self.projects_list.item(i)
            if current_item.text().endswith("◄──────"):
                current_item.setText(current_item.text().replace("◄──────", ""))
        
        item.setText(item.text() + " ◄──────")
    
    def load_chat_history_for_project(self):
        """Load chat history for the selected project."""
        if not self.current_project:
            return
            
        self.chat_display.clear()
        
        conn = sqlite3.connect(self.chat_history_db)
        cursor = conn.cursor()
        
        # Get the latest session for this project
        cursor.execute(
            "SELECT id FROM chat_sessions WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (self.current_project,)
        )
        session_row = cursor.fetchone()
        
        if session_row:
            session_id = session_row[0]
            
            # Get messages for this session
            cursor.execute(
                "SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            
            for role, content, timestamp in cursor.fetchall():
                self.display_message(role, content)
        
        conn.close()
    
    def display_message(self, role, content):
        """Display a message in the chat window."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if role == "user":
            formatted_content = f'<div style="margin: 5px 0;"><b>User (🧑):</b> {content}</div>'
        else:
            formatted_content = f'<div style="margin: 5px 0; color: #0066cc;"><b>Agent 🤖:</b> {content}</div>'
        
        cursor.insertHtml(formatted_content)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def send_message(self):
        """Send the user's message."""
        message = self.user_input.text().strip()
        if not message:
            return
        
        # Display user message
        self.display_message("user", message)
        self.user_input.clear()
        
        # Handle slash commands
        if message.startswith('/'):
            self.handle_slash_command(message)
        else:
            # Process regular message
            self.process_regular_message(message)
    
    def handle_slash_command(self, command):
        """Handle slash commands like /index, /build, etc."""
        if command == '/index':
            self.index_current_project()
        elif command == '/allindex':
            self.index_all_projects()
        elif command == '/build':
            self.build_current_project()
        elif command == '/test':
            self.test_current_file()
        elif command == '/clear':
            self.chat_display.clear()
        elif command == '/help':
            help_text = """
Available commands:
/index - Index current project
/allindex - Index all projects
/build - Build EXE for current project
/test - Test current file syntax
/clear - Clear chat
/help - Show this help
            """
            self.display_message("agent", help_text.strip())
        else:
            self.display_message("agent", f"Unknown command: {command}. Type /help for available commands.")
    
    def process_regular_message(self, message):
        """Process a regular user message through the orchestrator."""
        # This would normally connect to the orchestrator
        # For now, just simulate a response
        self.display_message("agent", "PLANNING... I'm analyzing your request. This would normally connect to the orchestrator to plan the task.")
        
        # Add to task log
        self.add_task_log_entry("TASK-001", "PLANNING", "Pending")
    
    def index_current_project(self):
        """Index the current project."""
        if self.current_project:
            self.display_message("agent", f"INDEXING... Started indexing project: {self.current_project}")
            self.add_task_log_entry("INDEX-001", "Indexing", "In Progress")
        else:
            self.display_message("agent", "No project selected. Please select a project first.")
    
    def index_all_projects(self):
        """Index all projects."""
        self.display_message("agent", "INDEXING... Started indexing all projects")
        self.add_task_log_entry("INDEX-ALL-001", "Indexing All", "In Progress")
    
    def build_current_project(self):
        """Build EXE for the current project."""
        if self.current_project:
            self.display_message("agent", f"BUILDING... Started building EXE for: {self.current_project}")
            self.add_task_log_entry("BUILD-001", "Building EXE", "In Progress")
        else:
            self.display_message("agent", "No project selected. Please select a project first.")
    
    def test_current_file(self):
        """Test current file syntax."""
        self.display_message("agent", "TESTING... Checking syntax of current file")
        self.add_task_log_entry("TEST-001", "Syntax Check", "In Progress")
    
    def add_task_log_entry(self, task_id, description, status):
        """Add an entry to the task log."""
        item_text = f"{task_id} - {description}: {status}"
        item = QListWidgetItem(item_text)
        self.task_list.addItem(item)
        
        # Auto-scroll to bottom
        self.task_list.scrollToBottom()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())