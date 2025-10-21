"""
Self-Modification System для II-Agent Pro
Позволяет агенту модифицировать свой собственный код
"""

import ast
import os
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SelfModifier:
    """
    Система автоматической модификации агента
    """
    
    def __init__(self):
        self.main_file = Path("main.py")
        self.backup_dir = Path("backups/self_modifications")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info("🔧 SelfModifier initialized")
    
    def backup_current_state(self) -> Path:
        """Создать бэкап текущего состояния main.py"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"main_{timestamp}.py"
        shutil.copy2(self.main_file, backup_file)
        logger.info(f"💾 Backup created: {backup_file}")
        return backup_file
    
    def add_import(self, import_statement: str) -> bool:
        """Добавить import в начало main.py"""
        try:
            with open(self.main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Проверяем что такого импорта ещё нет
            if import_statement in content:
                logger.info(f"ℹ️ Import already exists: {import_statement}")
                return True
            
            # Парсим существующие импорты
            tree = ast.parse(content)
            imports = [node for node in tree.body 
                      if isinstance(node, (ast.Import, ast.ImportFrom))]
            
            # Находим последний импорт
            if imports:
                last_import_line = imports[-1].end_lineno
                lines = content.split('\n')
                lines.insert(last_import_line, import_statement)
                new_content = '\n'.join(lines)
            else:
                # Если нет импортов, добавляем в начало
                new_content = import_statement + '\n' + content
            
            # Сохраняем
            with open(self.main_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            logger.info(f"✅ Import added: {import_statement}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add import: {e}")
            return False
    
    def add_endpoint(self, endpoint_code: str) -> bool:
        """Добавить новый эндпоинт в main.py"""
        try:
            with open(self.main_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Находим место для вставки (перед if __name__ == "__main__")
            insert_line = None
            for i in range(len(lines)-1, -1, -1):
                if 'if __name__ == "__main__"' in lines[i]:
                    insert_line = i - 1
                    break
            
            if insert_line is None:
                # Если не найдено, добавляем в конец
                insert_line = len(lines)
            
            # Вставляем код с отступом
            lines.insert(insert_line, '\n' + endpoint_code + '\n')
            
            # Сохраняем
            with open(self.main_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            logger.info(f"✅ Endpoint added")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add endpoint: {e}")
            return False
    
    def create_module(self, filename: str, code: str) -> bool:
        """Создать новый модуль в папке проекта"""
        try:
            module_path = Path(filename)
            with open(module_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            logger.info(f"✅ Module created: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create module: {e}")
            return False
    
    def add_dependency(self, package: str) -> bool:
        """Добавить зависимость в requirements.txt"""
        try:
            req_file = Path("requirements.txt")
            
            # Проверяем что зависимость ещё не добавлена
            with open(req_file, 'r', encoding='utf-8') as f:
                existing = f.read()
            
            package_name = package.split('==')[0].split('>=')[0]
            if package_name in existing:
                logger.info(f"ℹ️ Dependency already exists: {package}")
                return True
            
            # Добавляем
            with open(req_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{package}")
            
            logger.info(f"✅ Dependency added: {package}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add dependency: {e}")
            return False
    
    def test_syntax(self) -> bool:
        """Проверить синтаксис main.py"""
        try:
            result = subprocess.run(
                ['python', '-m', 'py_compile', str(self.main_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("✅ Syntax check passed")
                return True
            else:
                logger.error(f"❌ Syntax error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Syntax check failed: {e}")
            return False
    
    def restore_from_backup(self, backup_path: Path) -> bool:
        """Восстановить из бэкапа"""
        try:
            shutil.copy2(backup_path, self.main_file)
            logger.info(f"↩️ Restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to restore: {e}")
            return False
    
    async def self_modify(self, modification_request: Dict) -> Dict:
        """
        Главная функция самомодификации
        
        Args:
            modification_request: {
                "action": "add_feature",
                "module_name": "telegram_notifier",
                "module_code": "...",
                "import_statement": "from telegram_notifier import TelegramNotifier",
                "endpoint_code": "@app.post('/notify/telegram')...",
                "dependencies": ["python-telegram-bot==21.0"]
            }
        
        Returns:
            Dict с результатом операции
        """
        
        logger.info(f"🔧 Self-modification started: {modification_request.get('action')}")
        
        # 1. Создаём бэкап
        backup_path = self.backup_current_state()
        
        try:
            # 2. Создаём новый модуль (если указан)
            if modification_request.get("module_code"):
                success = self.create_module(
                    f"{modification_request['module_name']}.py",
                    modification_request['module_code']
                )
                if not success:
                    raise Exception("Failed to create module")
            
            # 3. Добавляем импорты (если указаны)
            if modification_request.get("import_statement"):
                success = self.add_import(modification_request['import_statement'])
                if not success:
                    raise Exception("Failed to add import")
            
            # 4. Добавляем эндпоинт (если указан)
            if modification_request.get("endpoint_code"):
                success = self.add_endpoint(modification_request['endpoint_code'])
                if not success:
                    raise Exception("Failed to add endpoint")
            
            # 5. Добавляем зависимости (если указаны)
            for dep in modification_request.get("dependencies", []):
                success = self.add_dependency(dep)
                if not success:
                    logger.warning(f"⚠️ Failed to add dependency: {dep}")
            
            # 6. Проверяем синтаксис
            if not self.test_syntax():
                raise Exception("Syntax check failed")
            
            logger.info("✅ Self-modification completed successfully")
            
            return {
                "status": "success",
                "message": "Agent successfully modified",
                "backup": str(backup_path),
                "note": "Restart Docker container to apply changes: docker-compose restart backend"
            }
            
        except Exception as e:
            logger.error(f"❌ Self-modification failed: {e}")
            
            # Откат к бэкапу
            self.restore_from_backup(backup_path)
            
            return {
                "status": "failed",
                "error": str(e),
                "message": "Modification failed, rolled back to backup",
                "backup_restored": str(backup_path)
            }
