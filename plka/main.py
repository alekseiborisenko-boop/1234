#!/usr/bin/env python3
"""
PLKA (Practical Local Code Assistant) v2.0
Main application entry point
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()