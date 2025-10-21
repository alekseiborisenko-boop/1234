# -*- coding: utf-8 -*-
"""
Model Hierarchy System
Система иерархии моделей с автоэскалацией и облачными fallback
"""
import logging
import os
import time
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ModelHierarchy:
    """Иерархическая система моделей с автоматической эскалацией"""
    
    def __init__(self, ollama_base_url: str = "http://host.docker.internal:11434"):
        self.ollama_base_url = ollama_base_url
        
        # Иерархия моделей от простых к сложным
        self.models = {
            "junior": {
                "name": "granite-code:3b",
                "description": "Быстрая модель для простых задач",
                "max_retries": 2,
                "timeout": 30
            },
            "middle": {
                "name": "qwen2.5-coder:7b",
                "description": "Специализированная модель для кода",
                "max_retries": 2,
                "timeout": 60
            },
            "senior": {
                "name": "qwen2.5:7b-instruct-q5_K_M",
                "description": "Продвинутая модель для сложных задач",
                "max_retries": 3,
                "timeout": 90
            },
            "expert": {
                "name": "hf.co/sizzlebop/Toucan-Qwen2.5-7B:latest",
                "description": "Экспертная локальная модель",
                "max_retries": 3,
                "timeout": 120
            }
        }
        
        self.stats = {
            "total_calls": 0,
            "escalations": 0,
            "cloud_calls": 0,
            "by_level": {level: 0 for level in self.models.keys()}
        }
    
    def call_model(
        self,
        prompt: str,
        level: str = "junior",
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """
        Вызов модели определённого уровня
        
        Args:
            prompt: Текст запроса
            level: Уровень модели (junior, middle, senior, expert)
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимум токенов в ответе
        """
        if level not in self.models:
            return {
                "success": False,
                "error": f"Unknown level: {level}",
                "available_levels": list(self.models.keys())
            }
        
        model_config = self.models[level]
        model_name = model_config["name"]
        
        self.stats["total_calls"] += 1
        self.stats["by_level"][level] += 1
        
        logger.info(f"🤖 Calling {level} model: {model_name}")
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens
                    }
                },
                timeout=model_config["timeout"]
            )
            
            response.raise_for_status()
            result = response.json()
            
            elapsed = time.time() - start_time
            
            logger.info(f"✅ {level} model responded in {elapsed:.2f}s")
            
            return {
                "success": True,
                "response": result.get("response", ""),
                "model": model_name,
                "level": level,
                "tokens": result.get("eval_count", 0),
                "elapsed": elapsed
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ {level} model timed out")
            return {
                "success": False,
                "error": f"Timeout after {model_config['timeout']}s",
                "model": model_name,
                "level": level
            }
            
        except Exception as e:
            logger.error(f"❌ {level} model error: {e}")
            return {
                "success": False,
                "error": str(e),
                "model": model_name,
                "level": level
            }
    
    def escalate(
        self,
        prompt: str,
        current_level: str = "junior",
        reason: str = None
    ) -> Dict[str, Any]:
        """
        Эскалация на следующий уровень модели
        
        Args:
            prompt: Текст запроса
            current_level: Текущий уровень
            reason: Причина эскалации
        """
        level_order = ["junior", "middle", "senior", "expert", "cloud"]
        
        if current_level not in level_order:
            current_level = "junior"
        
        current_index = level_order.index(current_level)
        
        if current_index >= len(level_order) - 1:
            logger.warning("🔝 Already at highest level, calling cloud expert")
            return call_cloud_expert(prompt)
        
        next_level = level_order[current_index + 1]
        
        logger.warning(f"🔼 Escalating from {current_level} to {next_level}")
        if reason:
            logger.info(f"   Reason: {reason}")
        
        self.stats["escalations"] += 1
        
        if next_level == "cloud":
            return call_cloud_expert(prompt)
        
        result = self.call_model(prompt, level=next_level, temperature=0.3)
        result["escalated"] = True
        result["from_level"] = current_level
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика использования моделей"""
        return {
            **self.stats,
            "cloud_percentage": round(
                (self.stats["cloud_calls"] / max(self.stats["total_calls"], 1)) * 100, 2
            ),
            "escalation_rate": round(
                (self.stats["escalations"] / max(self.stats["total_calls"], 1)) * 100, 2
            )
        }


# Глобальный экземпляр
model_hierarchy = ModelHierarchy()


# ==================== CLOUD EXPERTS ====================

def call_cloud_expert(prompt: str) -> Dict[str, Any]:
    """Вызов облачного эксперта с fallback на Gemini и локальные модели"""
    import os
    
    # Пробуем Groq (приоритет 1)
    groq_key = os.getenv("GROQ_API_KEY")
    
    if groq_key:
        logger.warning("""
╔══════════════════════════════════════════════════════════════╗
║  ⚠️  ВНИМАНИЕ: ИСПОЛЬЗУЕТСЯ GROQ API                         ║
║                                                              ║
║  Для работы из России необходим VPN!                         ║
║  Модель: Llama 3.3 70B (Groq)                                ║
╚══════════════════════════════════════════════════════════════╝
""")
        
        try:
            from groq import Groq
            
            client = Groq(api_key=groq_key)
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4096,
                timeout=30
            )
            
            logger.info(f"✅ Groq API успешно вызван")
            model_hierarchy.stats["cloud_calls"] += 1
            
            return {
                "success": True,
                "response": response.choices[0].message.content,
                "model": "llama-3.3-70b (Groq)",
                "cloud_used": True,
                "tokens": response.usage.total_tokens
            }
            
        except Exception as e:
            logger.error(f"❌ Groq API failed: {e}")
            logger.error("🔍 Возможные причины:")
            logger.error("   1. VPN не включен")
            logger.error("   2. Проблемы с сетью")
            logger.error("   3. Неверный API ключ")
            logger.info("🔄 Переключаюсь на Gemini...")
    
    # Fallback на Gemini (приоритет 2)
    return call_gemini_expert(prompt)


def call_gemini_expert(prompt: str) -> Dict[str, Any]:
    """Вызов Google Gemini API с fallback на локальные модели"""
    import os
    
    gemini_key = os.getenv("GOOGLE_GEMINI_KEY")
    
    if not gemini_key:
        logger.info("ℹ️  GOOGLE_GEMINI_KEY не найден, использую локальные модели")
        return call_local_expert(prompt)
    
    logger.warning("""
╔══════════════════════════════════════════════════════════════╗
║  ⚠️  ВНИМАНИЕ: ИСПОЛЬЗУЕТСЯ GOOGLE GEMINI API                ║
║                                                              ║
║  Для работы из России необходим VPN!                         ║
║  Модель: Gemini 2.0 Flash                                    ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,
                'max_output_tokens': 4096,
            }
        )
        
        logger.info(f"✅ Gemini API успешно вызван")
        model_hierarchy.stats["cloud_calls"] += 1
        
        return {
            "success": True,
            "response": response.text,
            "model": "gemini-2.0-flash",
            "cloud_used": True
        }
        
    except Exception as e:
        logger.error(f"❌ Gemini API failed: {e}")
        logger.info("🔄 Переключаюсь на локальную экспертную модель...")
        return call_local_expert(prompt)


def call_local_expert(prompt: str) -> Dict[str, Any]:
    """Вызов самой умной локальной модели (без интернета)"""
    logger.info("🏠 Вызов локальной экспертной модели...")
    
    result = model_hierarchy.call_model(
        prompt=prompt,
        level="expert",
        temperature=0.3
    )
    
    if result['success']:
        logger.info(f"✅ Локальная модель ответила ({result.get('tokens', 0)} токенов)")
    
    return {
        "success": result['success'],
        "response": result.get('response', ''),
        "model": "Toucan-Qwen2.5-7B (local)",
        "cloud_used": False,
        "tokens": result.get('tokens', 0)
    }