import os
import logging
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

logger = logging.getLogger(__name__)

class GigaChatAPI:
    def __init__(self):
        self.credentials = os.getenv('GIGACHAT_CREDENTIALS')
        self.client = None
        
    def connect(self):
        try:
            self.client = GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False
            )
            logger.info('GigaChat connected')
            return True
        except Exception as e:
            logger.error(f'GigaChat error: {e}')
            return False
    
    def generate(self, prompt: str, model: str = 'GigaChat-Max'):
        try:
            if not self.client:
                self.connect()
            
            response = self.client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    model=model,
                    temperature=0.7,
                    max_tokens=2048
                )
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f'GigaChat gen error: {e}')
            return f'Error: {str(e)}'
