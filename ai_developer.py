import os
import json
import logging
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

class AIDeveloper:
    '''AI-разработчик с автоматическим бэкапом и объяснениями'''
    
    def __init__(self, project_path: str = "E:/ii-agent/backend"):
        self.project_path = Path(project_path)
        self.backup_dir = self.project_path / "backups_ai"
        self.backup_dir.mkdir(exist_ok=True)
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.logger = logging.getLogger("ai_developer")
        self.model = "llama-3.3-70b-versatile"
        

    def _call_ai(self, prompt: str, provider: str = 'groq') -> str:
        """Universal AI call - Groq or Ollama"""
        
        if provider.lower() == 'ollama':
            self.logger.info(f'🤖 Using Ollama (local): qwen2.5:7b-instruct')
            try:
                response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        'model': 'llama-3.1-8b-instant',
                        'prompt': prompt,
                        'stream': False
                    },
                    timeout=120
                )
                
                if response.status_code == 200:
                    return response.json()['response']
                else:
                    raise Exception(f'Ollama error: {response.status_code}')
            except Exception as e:
                self.logger.error(f'❌ Ollama error: {e}')
                raise Exception(f'Ollama unavailable: {e}')
        
        

        elif provider.lower() == 'gigachat':
            self.logger.info(f'???? Using GigaChat API')
            try:
                from cloud_models import GigaChatAPI
                gigachat = GigaChatAPI()
                response = gigachat.chat(prompt)
                if response:
                    return response
                else:
                    raise Exception('GigaChat returned empty response')
            except Exception as e:
                self.logger.error(f'? GigaChat error: {e}')
                raise Exception(f'GigaChat unavailable: {e}')

        else:  # groq
            self.logger.info(f'🤖 Using Groq API: {self.model}')
            try:
                headers = {
                    'Authorization': f'Bearer {self.groq_api_key}',
                    'Content-Type': 'application/json'
                }
                payload = {
                    'model': self.model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.3,
                    'max_tokens': 2000
                }
                
                self.logger.info(f'📤 Sending to Groq: {self.model}')
                
                response = requests.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                self.logger.info(f'📥 Groq response status: {response.status_code}')
                
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                else:
                    error_text = response.text
                    self.logger.error(f'❌ Groq error {response.status_code}: {error_text}')
                    raise Exception(f'Groq API error: {response.status_code} - {error_text}')
            except Exception as e:
                self.logger.error(f'❌ Groq error: {e}')
                raise Exception(f'Groq unavailable (VPN required?): {e}')


    def analyze_task(self, task: str, provider: str = "groq") -> Dict:
        '''нализирует задачу и определяет что нужно изменить'''
        logger.info(f"🔍 Analyzing task: {task[:50]}...")
        
        prompt = f'''Ты - эксперт Python разработчик. роанализируй задачу:

: {task}

Т: II-Agent Pro (FastAPI + Ollama + RAG + веб-поиск)

предели:
1. акие файлы нужно изменить/создать
2. акие строки кода нужно модифицировать
3. раткий план реализации (3-5 шагов)

тветь ТЬ JSON:
{{
  "files_to_modify": ["file1.py", "file2.py"],
  "files_to_create": ["new_file.py"],
  "plan": ["Шаг 1", "Шаг 2", "Шаг 3"],
  "estimated_complexity": "low|medium|high"
}}'''

        response = self._call_ai(prompt, provider)
        
        try:
            analysis = json.loads(response)
            logger.info(f"✅ Analysis complete: {len(analysis.get('plan', []))} steps")
            return analysis
        except:
            return {
                "files_to_modify": [],
                "files_to_create": [],
                "plan": ["е удалось проанализировать задачу"],
                "estimated_complexity": "unknown"
            }
    
    def create_backup(self, files: List[str], task: str) -> str:
        '''Создаёт бэкап файлов перед изменением'''
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(exist_ok=True)
        
        metadata = {
            "backup_id": backup_id,
            "timestamp": timestamp,
            "task": task,
            "files": []
        }
        
        for file_path in files:
            full_path = self.project_path / file_path
            if full_path.exists():
                backup_file = backup_path / file_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                
                content = full_path.read_text(encoding='utf-8')
                backup_file.write_text(content, encoding='utf-8')
                
                metadata["files"].append({
                    "path": file_path,
                    "size": len(content),
                    "backed_up": True
                })
                logger.info(f"💾 Backed up: {file_path}")
        
        (backup_path / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        logger.info(f"✅ Backup created: {backup_id}")
        return backup_id
    
    def generate_solution(self, task: str, file_path: str, current_code: str = "") -> Dict:
        '''енерирует решение через Groq'''
        logger.info(f"🤖 Generating solution for: {file_path}")
        
        prompt = f'''Ты - эксперт Python разработчик. 

: {task}

: {file_path}

ТЩ  (если есть):
{current_code[:3000] if current_code else "# овый файл"}

Сгенерируй Ы код решения. твет в формате JSON:
{{
  "code": "полный код файла",
  "explanation": "краткое объяснение что изменил и зачем (3-5 предложений)",
  "changes_summary": "краткий список изменений"
}}'''

        response = self._call_groq(prompt, max_tokens=2000)
        
        try:
            solution = json.loads(response)
            logger.info(f"✅ Solution generated for {file_path}")
            return solution
        except:
            return {
                "code": current_code,
                "explanation": "е удалось сгенерировать решение",
                "changes_summary": "шибка генерации"
            }
    
    def apply_changes(self, file_path: str, new_code: str) -> bool:
        '''рименяет изменения к файлу'''
        try:
            full_path = self.project_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(new_code, encoding='utf-8')
            logger.info(f"✅ Applied changes to: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to apply changes: {e}")
            return False
    
    def get_diff(self, file_path: str, backup_id: str) -> str:
        '''олучает diff между текущей версией и бэкапом'''
        backup_file = self.backup_dir / backup_id / file_path
        current_file = self.project_path / file_path
        
        if not backup_file.exists():
            return "❌ Backup not found"
        
        backup_lines = backup_file.read_text(encoding='utf-8').splitlines()
        
        if current_file.exists():
            current_lines = current_file.read_text(encoding='utf-8').splitlines()
        else:
            current_lines = []
        
        diff = difflib.unified_diff(
            backup_lines,
            current_lines,
            fromfile=f'{file_path} (backup)',
            tofile=f'{file_path} (current)',
            lineterm=''
        )
        
        return '\n'.join(diff)
    
    def rollback(self, backup_id: str) -> bool:
        '''ткатывает изменения из бэкапа'''
        backup_path = self.backup_dir / backup_id
        metadata_file = backup_path / "metadata.json"
        
        if not metadata_file.exists():
            logger.error(f"❌ Backup not found: {backup_id}")
            return False
        
        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
        
        for file_info in metadata["files"]:
            file_path = file_info["path"]
            backup_file = backup_path / file_path
            current_file = self.project_path / file_path
            
            if backup_file.exists():
                content = backup_file.read_text(encoding='utf-8')
                current_file.write_text(content, encoding='utf-8')
                logger.info(f"⏮️ Restored: {file_path}")
        
        logger.info(f"✅ Rollback complete: {backup_id}")
        return True
    
    def list_backups(self) -> List[Dict]:
        '''Список всех бэкапов'''
        backups = []
        
        for backup_dir in sorted(self.backup_dir.iterdir(), reverse=True):
            metadata_file = backup_dir / "metadata.json"
            if metadata_file.exists():
                metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
                backups.append(metadata)
        
        return backups
    
    def _call_groq(self, prompt: str, max_tokens: int = 1000) -> str:
        '''ызов Groq API'''
        if not self.groq_api_key:
            logger.error("❌ GROQ_API_KEY not found")
            return "{}"
        
        try:
            response = requests.post(
                self.groq_url,
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"Groq API error: {response.status_code}")
                return "{}"
                
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return "{}"
