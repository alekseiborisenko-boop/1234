# -*- coding: utf-8 -*-
"""
Human Expert System
Система обращения к человеку-эксперту для решения сложных проблем
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from queue import Queue
import threading

logger = logging.getLogger(__name__)


class BackupSystem:
    """Система взаимодействия с человеком-экспертом"""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.queue_file = self.data_dir / "expert_queue.json"
        self.history_file = self.data_dir / "expert_history.json"
        
        self.pending_requests = []
        self.load_queue()
    
    def request_human_help(
        self,
        problem_type: str,
        description: str,
        error_log: str = None,
        code_snippet: str = None,
        context: Dict = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Создание запроса на помощь человеку
        
        Args:
            problem_type: Тип проблемы (syntax_error, logic_error, deployment, etc)
            description: Описание проблемы
            error_log: Лог ошибки
            code_snippet: Код с проблемой
            context: Дополнительный контекст
            priority: low, normal, high, critical
        """
        request_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        
        request = {
            "id": request_id,
            "type": problem_type,
            "description": description,
            "error_log": error_log,
            "code_snippet": code_snippet,
            "context": context or {},
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "resolved_at": None,
            "solution": None,
            "attempts": 0
        }
        
        self.pending_requests.append(request)
        self.save_queue()
        
        # Логируем красиво
        logger.warning(f"""
╔══════════════════════════════════════════════════════════════╗
║               🆘 ТРЕБУЕТСЯ ПОМОЩЬ ЭКСПЕРТА                   ║
╠══════════════════════════════════════════════════════════════╣
║ ID: {request_id}
║ Тип: {problem_type}
║ Приоритет: {priority.upper()}
║ 
║ ПРОБЛЕМА:
║ {description}
║
║ {'ЛОГ ОШИБКИ:' if error_log else ''}
║ {error_log if error_log else ''}
║
║ ДЕЙСТВИЯ:
║ 1. Откройте UI агента
║ 2. Перейдите в раздел "Помощь эксперта"
║ 3. Проверьте запрос #{request_id}
║ 4. Вставьте решение
╚══════════════════════════════════════════════════════════════╝
""")
        
        return {
            "success": True,
            "request_id": request_id,
            "status": "pending",
            "message": "Запрос создан. Ожидайте решения от эксперта."
        }
    
    def submit_solution(
        self,
        request_id: str,
        solution: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Человек вставляет решение"""
        try:
            request = self._find_request(request_id)
            
            if not request:
                return {"success": False, "error": "Request not found"}
            
            if request["status"] == "resolved":
                return {"success": False, "error": "Already resolved"}
            
            # Обновляем запрос
            request["status"] = "resolved"
            request["solution"] = solution
            request["notes"] = notes
            request["resolved_at"] = datetime.now().isoformat()
            
            # Перемещаем в историю
            self.save_to_history(request)
            self.pending_requests.remove(request)
            self.save_queue()
            
            logger.info(f"✅ Request {request_id} resolved by human expert")
            
            return {
                "success": True,
                "request_id": request_id,
                "solution": solution
            }
            
        except Exception as e:
            logger.error(f"Error submitting solution: {e}")
            return {"success": False, "error": str(e)}
    
    def get_pending_requests(
        self,
        priority_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Получить список ожидающих запросов"""
        requests = self.pending_requests.copy()
        
        if priority_filter:
            requests = [r for r in requests if r["priority"] == priority_filter]
        
        # Сортируем по приоритету и времени
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        requests.sort(
            key=lambda x: (priority_order.get(x["priority"], 99), x["created_at"])
        )
        
        return requests
    
    def get_request_details(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Получить детали запроса"""
        return self._find_request(request_id)
    
    def cancel_request(self, request_id: str) -> Dict[str, Any]:
        """Отменить запрос (агент решил сам)"""
        request = self._find_request(request_id)
        
        if not request:
            return {"success": False, "error": "Not found"}
        
        request["status"] = "cancelled"
        request["resolved_at"] = datetime.now().isoformat()
        
        self.pending_requests.remove(request)
        self.save_to_history(request)
        self.save_queue()
        
        return {"success": True}
    
    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """История обращений к эксперту"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                return history[-limit:]
            return []
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика обращений"""
        history = self.get_history(limit=100)
        
        total = len(history)
        resolved = len([h for h in history if h["status"] == "resolved"])
        cancelled = len([h for h in history if h["status"] == "cancelled"])
        
        avg_resolution_time = 0
        if resolved > 0:
            times = []
            for h in history:
                if h["status"] == "resolved" and h["resolved_at"]:
                    created = datetime.fromisoformat(h["created_at"])
                    resolved_dt = datetime.fromisoformat(h["resolved_at"])
                    times.append((resolved_dt - created).total_seconds())
            
            if times:
                avg_resolution_time = sum(times) / len(times)
        
        return {
            "total_requests": total,
            "pending": len(self.pending_requests),
            "resolved": resolved,
            "cancelled": cancelled,
            "avg_resolution_time_seconds": round(avg_resolution_time, 2)
        }
    
    def _find_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Найти запрос по ID"""
        for req in self.pending_requests:
            if req["id"] == request_id:
                return req
        return None
    
    def load_queue(self):
        """Загрузить очередь из файла"""
        try:
            if self.queue_file.exists():
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    self.pending_requests = json.load(f)
        except Exception as e:
            logger.error(f"Error loading queue: {e}")
            self.pending_requests = []
    
    def save_queue(self):
        """Сохранить очередь в файл"""
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(self.pending_requests, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving queue: {e}")
    
    def save_to_history(self, request: Dict[str, Any]):
        """Сохранить в историю"""
        try:
            history = []
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            history.append(request)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving to history: {e}")


# Глобальный экземпляр
human_expert = HumanExpertSystem()
