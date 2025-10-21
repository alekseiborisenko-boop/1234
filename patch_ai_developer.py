import re
import sys

# Read ai_developer.py
ai_dev = open(r'E:\ii-agent\backend\ai_developer.py', 'r', encoding='utf-8').read()

# New method for provider selection
new_method = """
    def _call_ai(self, prompt: str, provider: str = 'groq') -> str:
        \"\"\"Universal AI call - Groq or Ollama\"\"\"
        
        if provider.lower() == 'ollama':
            self.logger.info(f'🤖 Using Ollama (local): qwen2.5:7b-instruct')
            try:
                response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        'model': 'qwen2.5:7b-instruct',
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
        
        else:  # groq
            self.logger.info(f'🤖 Using Groq API: {self.model}')
            try:
                response = requests.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization': f'Bearer {self.groq_api_key}'},
                    json={
                        'model': self.model,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'temperature': 0.3
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                else:
                    raise Exception(f'Groq API error: {response.status_code}')
            except Exception as e:
                self.logger.error(f'❌ Groq error: {e}')
                raise Exception(f'Groq unavailable (VPN required?): {e}')
"""

# Find class and add method
class_match = re.search(r'(class AIDeveloper:.*?def __init__.*?(?=\n    def))', ai_dev, re.DOTALL)
if class_match:
    insert_pos = class_match.end()
    ai_dev = ai_dev[:insert_pos] + '\n' + new_method + ai_dev[insert_pos:]
    print('✅ Method _call_ai added')
else:
    print('❌ Class not found')
    sys.exit(1)

# Update analyze_task signature
ai_dev = re.sub(
    r'def analyze_task\(self, task: str\)',
    'def analyze_task(self, task: str, provider: str = "groq")',
    ai_dev
)
print('✅ analyze_task signature updated')

# Update _call_groq calls to _call_ai
ai_dev = re.sub(
    r'self\._call_groq\(prompt\)',
    'self._call_ai(prompt, provider)',
    ai_dev
)
print('✅ Method calls updated')

# Save
open(r'E:\ii-agent\backend\ai_developer.py', 'w', encoding='utf-8').write(ai_dev)
print('✅ Backend updated with provider selection!')
