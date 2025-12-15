#!/usr/bin/env python3
"""
Test script to verify PLKA components are working correctly
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_components():
    print("Testing PLKA components...")
    print("="*50)
    
    # Test 1: Project Manager
    try:
        from core.project_manager import ProjectManager
        pm = ProjectManager()
        projects = pm.list_projects()
        print("✅ ProjectManager: OK")
        print(f"   Found {len(projects)} projects")
    except Exception as e:
        print(f"❌ ProjectManager: {e}")
    
    # Test 2: RAG Service
    try:
        from core.rag_service import RAGService
        rag = RAGService()
        print("✅ RAGService: OK")
        print(f"   Config loaded: {list(rag.config.keys())}")
    except Exception as e:
        print(f"❌ RAGService: {e}")
    
    # Test 3: File Editor
    try:
        from core.file_editor import FileEditor
        editor = FileEditor()
        print("✅ FileEditor: OK")
        print(f"   Validator base path: {editor.validator.base_path}")
    except Exception as e:
        print(f"❌ FileEditor: {e}")
    
    # Test 4: Orchestrator
    try:
        from core.orchestrator import Orchestrator
        orchestrator = Orchestrator()
        print("✅ Orchestrator: OK")
        print(f"   DB path: {orchestrator.db_path}")
    except Exception as e:
        print(f"❌ Orchestrator: {e}")
    
    # Test 5: Experience Manager
    try:
        from core.experience_manager import ExperienceManager
        exp_manager = ExperienceManager()
        patterns = exp_manager.get_stable_patterns()
        print("✅ ExperienceManager: OK")
        print(f"   Found {len(patterns)} stable patterns")
    except Exception as e:
        print(f"❌ ExperienceManager: {e}")
    
    # Test 6: Build Manager
    try:
        from core.build_manager import BuildManager
        build_manager = BuildManager()
        print("✅ BuildManager: OK")
        print(f"   Dist path: {build_manager.dist_path}")
    except Exception as e:
        print(f"❌ BuildManager: {e}")
    
    # Test 7: LLM Client
    try:
        from core.llm_client import LLMClient
        llm_client = LLMClient()
        print("✅ LLMClient: OK")
        print(f"   Hardware class: {llm_client.config['hardware_class']}")
    except Exception as e:
        print(f"❌ LLMClient: {e}")
    
    print("\n" + "="*50)
    print("Component testing completed!")

if __name__ == "__main__":
    test_components()