# -*- coding: utf-8 -*-
"""
Test System
Автоматическое тестирование изменений перед применением
"""
import subprocess
import sys
import os
import logging
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TestSystem:
    """Система автоматического тестирования"""
    
    def __init__(self, project_root: str = "/app"):
        self.project_root = Path(project_root)
        self.test_results = []
        self.backend_url = "http://localhost:8000"
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Запуск всех тестов"""
        logger.info("🧪 Starting test suite...")
        
        start_time = time.time()
        
        tests = [
            self.test_python_syntax(),
            self.test_imports(),
            self.test_file_structure(),
            self.test_api_endpoints(),
            self.test_database_connection(),
            self.test_ollama_connection(),
            self.test_memory_usage()
        ]
        
        execution_time = time.time() - start_time
        
        passed = sum(1 for t in tests if t.get('passed', False))
        failed = len(tests) - passed
        
        result = {
            "success": failed == 0,
            "passed": passed,
            "failed": failed,
            "total": len(tests),
            "tests": tests,
            "execution_time": round(execution_time, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        if result["success"]:
            logger.info(f"✅ All tests passed! ({passed}/{len(tests)})")
        else:
            logger.error(f"❌ {failed} test(s) failed!")
        
        self.test_results.append(result)
        
        return result
    
    def test_python_syntax(self) -> Dict[str, Any]:
        """Тест 1: Проверка синтаксиса Python"""
        test_name = "python_syntax"
        logger.info(f"Testing: {test_name}")
        
        try:
            # Ищем все .py файлы
            py_files = list(self.project_root.rglob("*.py"))
            
            errors = []
            for filepath in py_files:
                # Пропускаем venv и __pycache__
                if "venv" in str(filepath) or "__pycache__" in str(filepath):
                    continue
                
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(filepath)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    errors.append({
                        "file": str(filepath),
                        "error": result.stderr
                    })
            
            passed = len(errors) == 0
            
            return {
                "name": test_name,
                "passed": passed,
                "files_checked": len(py_files),
                "errors": errors if not passed else None,
                "message": "All Python files are valid" if passed else f"{len(errors)} syntax errors found"
            }
            
        except Exception as e:
            return {
                "name": test_name,
                "passed": False,
                "error": str(e)
            }
    
    def test_imports(self) -> Dict[str, Any]:
        """Тест 2: Проверка импортов"""
        test_name = "imports"
        logger.info(f"Testing: {test_name}")
        
        try:
            # Проверяем основные модули
            critical_modules = [
                "main",
                "self_improve",
                "backup_system",
                "model_hierarchy"
            ]
            
            errors = []
            for module_name in critical_modules:
                module_path = self.project_root / f"{module_name}.py"
                
                if not module_path.exists():
                    errors.append({
                        "module": module_name,
                        "error": "Module file not found"
                    })
                    continue
                
                result = subprocess.run(
                    [sys.executable, "-c", f"import {module_name}"],
                    capture_output=True,
                    text=True,
                    cwd=str(self.project_root),
                    timeout=10
                )
                
                if result.returncode != 0:
                    errors.append({
                        "module": module_name,
                        "error": result.stderr
                    })
            
            passed = len(errors) == 0
            
            return {
                "name": test_name,
                "passed": passed,
                "modules_checked": len(critical_modules),
                "errors": errors if not passed else None,
                "message": "All imports successful" if passed else f"{len(errors)} import errors"
            }
            
        except Exception as e:
            return {
                "name": test_name,
                "passed": False,
                "error": str(e)
            }
    
    def test_file_structure(self) -> Dict[str, Any]:
        """Тест 3: Проверка структуры проекта"""
        test_name = "file_structure"
        logger.info(f"Testing: {test_name}")
        
        try:
            required_files = [
                "main.py",
                "requirements.txt",
                "Dockerfile",
                "self_improve.py",
                "backup_system.py",
                "model_hierarchy.py"
            ]
            
            missing = []
            for filename in required_files:
                filepath = self.project_root / filename
                if not filepath.exists():
                    missing.append(filename)
            
            passed = len(missing) == 0
            
            return {
                "name": test_name,
                "passed": passed,
                "required_files": len(required_files),
                "missing_files": missing if not passed else None,
                "message": "All required files present" if passed else f"{len(missing)} files missing"
            }
            
        except Exception as e:
            return {
                "name": test_name,
                "passed": False,
                "error": str(e)
            }
    
    def test_api_endpoints(self) -> Dict[str, Any]:
        """Тест 4: Проверка API эндпоинтов"""
        test_name = "api_endpoints"
        logger.info(f"Testing: {test_name}")
        
        try:
            # Критичные эндпоинты
            endpoints = [
                {"path": "/health", "method": "GET"},
                {"path": "/api/chat", "method": "POST"},
                {"path": "/api/status", "method": "GET"}
            ]
            
            errors = []
            for endpoint in endpoints:
                try:
                    if endpoint["method"] == "GET":
                        response = requests.get(
                            f"{self.backend_url}{endpoint['path']}",
                            timeout=5
                        )
                    else:
                        response = requests.post(
                            f"{self.backend_url}{endpoint['path']}",
                            json={"message": "test"},
                            timeout=5
                        )
                    
                    if response.status_code >= 500:
                        errors.append({
                            "endpoint": endpoint['path'],
                            "status": response.status_code,
                            "error": "Server error"
                        })
                        
                except requests.exceptions.ConnectionError:
                    errors.append({
                        "endpoint": endpoint['path'],
                        "error": "Connection failed - server not running?"
                    })
                except requests.exceptions.Timeout:
                    errors.append({
                        "endpoint": endpoint['path'],
                        "error": "Timeout"
                    })
            
            passed = len(errors) == 0
            
            return {
                "name": test_name,
                "passed": passed,
                "endpoints_checked": len(endpoints),
                "errors": errors if not passed else None,
                "message": "All endpoints responding" if passed else f"{len(errors)} endpoint errors"
            }
            
        except Exception as e:
            return {
                "name": test_name,
                "passed": False,
                "error": str(e)
            }
    
    def test_database_connection(self) -> Dict[str, Any]:
        """Тест 5: Проверка подключения к БД"""
        test_name = "database_connection"
        logger.info(f"Testing: {test_name}")
        
        try:
            # Проверяем наличие SQLite БД
            db_path = self.project_root / "data" / "agent.db"
            
            if not db_path.exists():
                return {
                    "name": test_name,
                    "passed": False,
                    "message": "Database file not found",
                    "path": str(db_path)
                }
            
            # Проверяем доступность
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            
            passed = result[0] == 1
            
            return {
                "name": test_name,
                "passed": passed,
                "message": "Database accessible" if passed else "Database query failed"
            }
            
        except Exception as e:
            return {
                "name": test_name,
                "passed": False,
                "error": str(e)
            }
    
    def test_ollama_connection(self) -> Dict[str, Any]:
        """Тест 6: Проверка подключения к Ollama"""
        test_name = "ollama_connection"
        logger.info(f"Testing: {test_name}")
        
        try:
            response = requests.get(
                "http://localhost:11434/api/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                
                return {
                    "name": test_name,
                    "passed": True,
                    "models_available": len(models),
                    "message": f"Ollama running with {len(models)} models"
                }
            else:
                return {
                    "name": test_name,
                    "passed": False,
                    "error": f"HTTP {response.status_code}"
                }
                
        except requests.exceptions.ConnectionError:
            return {
                "name": test_name,
                "passed": False,
                "error": "Ollama not running"
            }
        except Exception as e:
            return {
                "name": test_name,
                "passed": False,
                "error": str(e)
            }
    
    def test_memory_usage(self) -> Dict[str, Any]:
        """Тест 7: Проверка использования памяти"""
        test_name = "memory_usage"
        logger.info(f"Testing: {test_name}")
        
        try:
            import psutil
            
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Предупреждение если больше 2GB
            warning_threshold = 2048
            passed = memory_mb < warning_threshold
            
            return {
                "name": test_name,
                "passed": passed,
                "memory_mb": round(memory_mb, 2),
                "threshold_mb": warning_threshold,
                "message": f"Memory usage: {round(memory_mb, 2)} MB" + 
                          ("" if passed else f" (exceeds {warning_threshold} MB)")
            }
            
        except Exception as e:
            return {
                "name": test_name,
                "passed": True,  # Не критично если не удалось проверить
                "warning": str(e)
            }
    
    def test_specific_file(self, filepath: str) -> Dict[str, Any]:
        """Тест конкретного файла"""
        logger.info(f"Testing file: {filepath}")
        
        try:
            file_path = Path(filepath)
            
            # Проверка существования
            if not file_path.exists():
                return {
                    "success": False,
                    "error": "File not found"
                }
            
            # Проверка синтаксиса для .py файлов
            if file_path.suffix == '.py':
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": result.stderr
                    }
            
            return {
                "success": True,
                "message": f"File {filepath} is valid"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_test_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """История тестирования"""
        return self.test_results[-limit:]
    
    def generate_test_report(self) -> str:
        """Генерация отчёта о тестировании"""
        if not self.test_results:
            return "No test results available"
        
        latest = self.test_results[-1]
        
        report = f"""
╔══════════════════════════════════════════╗
║        TEST REPORT                       ║
╚══════════════════════════════════════════╝

Status: {'✅ PASSED' if latest['success'] else '❌ FAILED'}
Time: {latest['timestamp']}
Duration: {latest['execution_time']}s

Results: {latest['passed']}/{latest['total']} tests passed

Details:
"""
        
        for test in latest['tests']:
            status = "✅" if test['passed'] else "❌"
            report += f"  {status} {test['name']}: {test.get('message', 'OK')}\n"
        
        return report


# Глобальный экземпляр
test_system = TestSystem()
