# -*- coding: utf-8 -*-
"""
II-Agent Self-Improvement System
Система самообучения и самовосстановления
"""
import os
import re
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ==================== КОНФИГУРАЦИЯ ====================

CODE_DIR = Path("/app")
BACKUP_DIR = Path("/app/backups")
LOGS_FILE = Path("/app/logs/agent.log")

BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ==================== ВЫЗОВ LLM ====================

def call_llm_for_analysis(prompt: str) -> str:
    """Вызов LLM для анализа проблем"""
    try:
        import requests
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json().get('response', '')
        else:
            logger.error(f"LLM call failed: {response.status_code}")
            return ""
            
    except Exception as e:
        logger.error(f"LLM analysis error: {e}")
        return ""

# ==================== АНАЛИЗ ЛОГОВ ====================

def analyze_logs(hours: int = 1) -> List[Dict[str, Any]]:
    """Анализ последних логов для поиска проблем"""
    try:
        if not LOGS_FILE.exists():
            logger.warning("Log file not found")
            return []
        
        # Читаем последние N строк
        with open(LOGS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-1000:]  # Последние 1000 строк
        
        issues = []
        
        # Паттерны ошибок
        error_patterns = {
            'timeout': r'Timeout|таймаут',
            'empty_response': r'Пустой ответ|Empty response',
            'no_info': r'Информация отсутствует|не найдено информации',
            'model_error': r'Model error|Модель.*ошибк',
            'parse_error': r'Parse error|парсинг.*ошибк',
            'api_error': r'API error|API.*ошибк',
            'connection_error': r'Connection.*error|соединение.*ошибк',
            'memory_error': r'Memory.*error|памят.*ошибк'
        }
        
        for line in lines:
            for error_type, pattern in error_patterns.items():
                if re.search(pattern, line, re.I):
                    issues.append({
                        'type': error_type,
                        'line': line.strip(),
                        'timestamp': datetime.now().isoformat()
                    })
        
        # Группируем по типу
        grouped = {}
        for issue in issues:
            error_type = issue['type']
            if error_type not in grouped:
                grouped[error_type] = []
            grouped[error_type].append(issue)
        
        # Формируем отчёт
        report = []
        for error_type, errors in grouped.items():
            if len(errors) > 3:  # Только частые ошибки
                report.append({
                    'type': error_type,
                    'count': len(errors),
                    'severity': 'high' if len(errors) > 10 else 'medium',
                    'sample': errors[-1]['line']
                })
        
        return report
        
    except Exception as e:
        logger.error(f"Log analysis error: {e}")
        return []

# ==================== ЧТЕНИЕ КОДА ====================

def read_code_file(filename: str = "main.py") -> Optional[Dict[str, Any]]:
    """Чтение исходного кода"""
    try:
        filepath = CODE_DIR / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Разбиваем на функции
        functions = {}
        current_func = None
        func_lines = []
        
        for line in content.split('\n'):
            if line.startswith('def ') or line.startswith('async def '):
                if current_func:
                    functions[current_func] = '\n'.join(func_lines)
                match = re.match(r'(?:async\s+)?def\s+(\w+)\s*\(', line)
                if match:
                    current_func = match.group(1)
                    func_lines = [line]
            elif current_func:
                func_lines.append(line)
        
        if current_func:
            functions[current_func] = '\n'.join(func_lines)
        
        return {
            'full_code': content,
            'functions': functions,
            'lines': len(content.split('\n'))
        }
        
    except Exception as e:
        logger.error(f"Code reading error: {e}")
        return None

# ==================== LLM АНАЛИЗ КОДА ====================

def analyze_issue_with_llm(issue: Dict[str, Any], code_context: str) -> Dict[str, Any]:
    """Анализ проблемы через LLM"""
    try:
        prompt = f"""Ты — эксперт по Python и отладке кода.

Проблема: {issue['type']} (встречается {issue['count']} раз)
Уровень: {issue['severity']}
Пример: {issue['sample']}

Контекст кода:
{code_context[:2000]} # Первые 2000 символов

Задача:
1. Определи причину проблемы
2. Предложи конкретное исправление
3. Напиши улучшенный код функции

Формат ответа:
ПРИЧИНА: <описание>
РЕШЕНИЕ: <описание>
КОД: <исправленный код>
"""
        
        llm_response = call_llm_for_analysis(prompt)
        
        # Парсим ответ LLM
        cause = ""
        solution = ""
        code = ""
        
        if "ПРИЧИНА:" in llm_response:
            cause = llm_response.split("ПРИЧИНА:")[1].split("РЕШЕНИЕ:")[0].strip()
        if "РЕШЕНИЕ:" in llm_response:
            solution = llm_response.split("РЕШЕНИЕ:")[1].split("КОД:")[0].strip()
        if "КОД:" in llm_response:
            code = llm_response.split("КОД:")[1].strip()
        
        return {
            'llm_analysis': True,
            'cause': cause,
            'solution': solution,
            'suggested_code': code
        }
        
    except Exception as e:
        logger.error(f"LLM analysis error: {e}")
        return {'llm_analysis': False, 'error': str(e)}

# ==================== ГЕНЕРАЦИЯ ИСПРАВЛЕНИЙ ====================

def generate_fix_for_issue(issue: Dict[str, Any], code_context: Dict[str, Any]) -> Dict[str, Any]:
    """Генерация исправления для проблемы"""
    
    # Базовые исправления по шаблону
    template_fixes = {
        'timeout': {
            'description': 'Частые таймауты модели',
            'suggestions': [
                'Увеличить timeout в call_model() до 180 секунд',
                'Добавить retry механизм',
                'Использовать более быструю модель по умолчанию'
            ],
            'code_changes': {
                'file': 'main.py',
                'function': 'call_model',
                'change': 'timeout parameter: 120 -> 180'
            }
        },
        'empty_response': {
            'description': 'Модель возвращает пустые ответы',
            'suggestions': [
                'Улучшить промпт с примерами',
                'Добавить fallback на другую модель',
                'Увеличить max_tokens'
            ]
        },
        'no_info': {
            'description': 'Модель часто говорит "информация отсутствует"',
            'suggestions': [
                'Смягчить промпт',
                'Добавить примеры успешных ответов',
                'Увеличить количество источников'
            ]
        },
        'model_error': {
            'description': 'Ошибки при вызове модели',
            'suggestions': [
                'Добавить обработку специфичных ошибок',
                'Улучшить retry логику',
                'Добавить fallback модель'
            ]
        },
        'parse_error': {
            'description': 'Ошибки парсинга сайтов',
            'suggestions': [
                'Улучшить обработку невалидного HTML',
                'Добавить больше fallback стратегий',
                'Увеличить timeout парсинга'
            ]
        },
        'api_error': {
            'description': 'Ошибки внешних API',
            'suggestions': [
                'Добавить retry с exponential backoff',
                'Улучшить обработку rate limits',
                'Добавить кэширование результатов'
            ]
        },
        'connection_error': {
            'description': 'Ошибки соединения',
            'suggestions': [
                'Добавить проверку соединения перед запросом',
                'Увеличить timeout для медленных сетей',
                'Добавить offline режим'
            ]
        },
        'memory_error': {
            'description': 'Проблемы с памятью',
            'suggestions': [
                'Оптимизировать загрузку данных',
                'Добавить очистку кэша',
                'Уменьшить batch size'
            ]
        }
    }
    
    base_fix = template_fixes.get(issue['type'], {
        'description': f"Неизвестная проблема: {issue['type']}",
        'suggestions': ['Требуется ручной анализ']
    })
    
    # Добавляем LLM анализ
    relevant_code = ""
    if code_context and 'functions' in code_context:
        # Находим релевантную функцию
        for func_name, func_code in code_context['functions'].items():
            if issue['type'] in func_name.lower():
                relevant_code = func_code
                break
        
        if not relevant_code and code_context['functions']:
            # Берём первую функцию
            relevant_code = list(code_context['functions'].values())[0]
    
    llm_analysis = analyze_issue_with_llm(issue, relevant_code)
    
    # Объединяем
    return {
        **base_fix,
        **llm_analysis,
        'issue_type': issue['type'],
        'count': issue['count'],
        'severity': issue['severity']
    }

# ==================== СОЗДАНИЕ ПАТЧА ====================

def create_patch(fix: Dict[str, Any], code_data: Dict[str, Any]) -> Optional[str]:
    """Создание патча для кода"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        patch_file = BACKUP_DIR / f"patch_{timestamp}.json"
        
        patch = {
            'timestamp': timestamp,
            'created_at': datetime.now().isoformat(),
            'issue_type': fix.get('issue_type', 'unknown'),
            'description': fix['description'],
            'suggestions': fix['suggestions'],
            'llm_analysis': fix.get('llm_analysis', False),
            'llm_cause': fix.get('cause', ''),
            'llm_solution': fix.get('solution', ''),
            'suggested_code': fix.get('suggested_code', ''),
            'changes': fix.get('code_changes', {}),
            'status': 'pending',
            'severity': fix.get('severity', 'medium')
        }
        
        with open(patch_file, 'w', encoding='utf-8') as f:
            json.dump(patch, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Patch created: {patch_file}")
        return str(patch_file)
        
    except Exception as e:
        logger.error(f"Patch creation error: {e}")
        return None

# ==================== ПРИМЕНЕНИЕ ПАТЧА ====================

def apply_patch(patch_file: Path, auto_approve: bool = False) -> bool:
    """Применение патча к коду"""
    try:
        with open(patch_file, 'r', encoding='utf-8') as f:
            patch = json.load(f)
        
        if not auto_approve and patch.get('severity') == 'high':
            logger.warning(f"High severity patch requires manual approval: {patch_file}")
            return False
        
        # Создаём бэкап
        timestamp = patch.get('timestamp', datetime.now().strftime('%Y%m%d_%H%M%S'))
        backup_file = BACKUP_DIR / f"main_backup_{timestamp}.py"
        original_file = CODE_DIR / "main.py"
        
        if not original_file.exists():
            logger.error("main.py not found")
            return False
        
        with open(original_file, 'r', encoding='utf-8') as f:
            original_code = f.read()
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original_code)
        
        logger.info(f"Backup created: {backup_file}")
        
        # Применяем изменения если есть suggested_code
        if patch.get('suggested_code'):
            function_name = patch.get('changes', {}).get('function')
            if function_name:
                # Находим функцию и заменяем
                new_code = re.sub(
                    rf'def {function_name}\([^)]*\):.*?(?=\ndef |\nclass |\Z)',
                    patch['suggested_code'],
                    original_code,
                    flags=re.DOTALL
                )
                
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(new_code)
                
                logger.info(f"✅ Code modified: {function_name}")
        
        # Обновляем статус патча
        patch['status'] = 'applied'
        patch['applied_at'] = datetime.now().isoformat()
        
        with open(patch_file, 'w', encoding='utf-8') as f:
            json.dump(patch, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Patch applied: {patch_file}")
        return True
        
    except Exception as e:
        logger.error(f"Patch application error: {e}")
        return False

# ==================== МЕТРИКИ ====================

def track_improvement_metrics() -> Dict[str, Any]:
    """Отслеживание метрик улучшения"""
    try:
        metrics = {
            'patches_created': 0,
            'patches_applied': 0,
            'patches_pending': 0,
            'errors_by_type': {},
            'last_self_diagnosis': None
        }
        
        if not BACKUP_DIR.exists():
            return metrics
        
        for patch_file in BACKUP_DIR.glob("patch_*.json"):
            try:
                with open(patch_file, 'r') as f:
                    patch = json.load(f)
                
                metrics['patches_created'] += 1
                
                if patch.get('status') == 'applied':
                    metrics['patches_applied'] += 1
                elif patch.get('status') == 'pending':
                    metrics['patches_pending'] += 1
                
                issue_type = patch.get('issue_type', 'unknown')
                if issue_type not in metrics['errors_by_type']:
                    metrics['errors_by_type'][issue_type] = 0
                metrics['errors_by_type'][issue_type] += 1
                
                # Последняя диагностика
                created_at = patch.get('created_at')
                if created_at:
                    if not metrics['last_self_diagnosis'] or created_at > metrics['last_self_diagnosis']:
                        metrics['last_self_diagnosis'] = created_at
                        
            except Exception as e:
                logger.error(f"Error reading patch {patch_file.name}: {e}")
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics tracking error: {e}")
        return {}

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def self_diagnose() -> Dict[str, Any]:
    """Полная самодиагностика агента"""
    try:
        logger.info("=== SELF-DIAGNOSIS STARTED ===")
        
        # 1. Анализ логов
        logger.info("Step 1: Analyzing logs...")
        issues = analyze_logs(hours=1)
        
        if not issues:
            logger.info("✅ No critical issues found")
            return {
                'status': 'healthy',
                'issues': [],
                'suggestions': [],
                'metrics': track_improvement_metrics()
            }
        
        logger.info(f"⚠️ Found {len(issues)} issue types")
        
        # 2. Чтение кода
        logger.info("Step 2: Reading code...")
        code_data = read_code_file("main.py")
        
        if not code_data:
            logger.error("❌ Cannot read code")
            return {'status': 'error', 'message': 'Cannot read code'}
        
        # 3. Генерация исправлений (с LLM)
        logger.info("Step 3: Generating fixes with LLM...")
        fixes = []
        
        for issue in issues:
            logger.info(f"Analyzing {issue['type']} with LLM...")
            fix = generate_fix_for_issue(issue, code_data)
            fixes.append(fix)
        
        # 4. Создание патчей
        logger.info("Step 4: Creating patches...")
        patches = []
        
        for fix in fixes:
            patch_file = create_patch(fix, code_data)
            if patch_file:
                patches.append(patch_file)
        
        logger.info(f"=== SELF-DIAGNOSIS COMPLETED: {len(patches)} patches created ===")
        
        return {
            'status': 'issues_found',
            'issues_count': len(issues),
            'fixes': fixes,
            'patches': patches,
            'code_health': {
                'total_lines': code_data['lines'],
                'total_functions': len(code_data['functions'])
            },
            'metrics': track_improvement_metrics()
        }
        
    except Exception as e:
        logger.error(f"Self-diagnosis error: {e}")
        return {'status': 'error', 'message': str(e)}

# ==================== СПИСОК ПАТЧЕЙ ====================

def list_patches() -> List[Dict[str, Any]]:
    """Список всех патчей"""
    patches = []
    if BACKUP_DIR.exists():
        for patch_file in BACKUP_DIR.glob("patch_*.json"):
            try:
                with open(patch_file, 'r', encoding='utf-8') as f:
                    patch = json.load(f)
                patch['filename'] = patch_file.name
                patches.append(patch)
            except Exception as e:
                logger.error(f"Error reading patch {patch_file.name}: {e}")
    
    patches.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return patches

def get_patch(patch_filename: str) -> Optional[Dict[str, Any]]:
    """Получить патч по имени"""
    patch_file = BACKUP_DIR / patch_filename
    if patch_file.exists():
        try:
            with open(patch_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading patch {patch_filename}: {e}")
    return None

# ==================== АВТОУСТАНОВКА ПАКЕТОВ ====================

def auto_install_package(package_name: str) -> Dict[str, Any]:
    """Автоматическая установка Python пакета"""
    try:
        logger.info(f"📦 Installing package: {package_name}")
        
        # Проверка безопасности
        if not re.match(r'^[a-zA-Z0-9_-]+$', package_name):
            return {"success": False, "error": "Invalid package name"}
        
        # Установка
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Package {package_name} installed")
            return {"success": True, "output": result.stdout}
        else:
            logger.error(f"❌ Package {package_name} installation failed")
            return {"success": False, "error": result.stderr}
            
    except Exception as e:
        logger.error(f"Installation error: {e}")
        return {"success": False, "error": str(e)}
