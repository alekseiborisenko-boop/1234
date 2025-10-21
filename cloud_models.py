"""
cloud_models.py - GigaChat integration для II-Agent Pro
"""
import os
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class GigaChatAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('GIGACHAT_API_KEY')
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        self.access_token = None
        
        if self.api_key:
            self._get_access_token()
    
    def _get_access_token(self):
        try:
            import uuid
            import base64
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'RqUID': str(uuid.uuid4()),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data={'scope': 'GIGACHAT_API_PERS'},
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                self.access_token = response.json()['access_token']
                logger.info("GigaChat connected")
            else:
                logger.error(f"GigaChat auth error: {response.status_code}")
        except Exception as e:
            logger.error(f"GigaChat auth exception: {e}")
    
    def chat(self, prompt: str, model: str = "GigaChat-Max") -> Optional[str]:
        if not self.access_token:
            self._get_access_token()
            if not self.access_token:
                return None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 2000
            }
            
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=payload,
                verify=False,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"GigaChat API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"GigaChat exception: {e}")
            return None
