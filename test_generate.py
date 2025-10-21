import requests
import json

# Тестируем endpoint генерации
url = 'http://localhost:8000/ai-developer/generate'

data = {
    'task': 'Тестовая задача',
    'analysis': {'steps': []},
    'provider': 'ollama'
}

print('📡 тправляем запрос на', url)
print('📦 анные:', json.dumps(data, ensure_ascii=False))

try:
    response = requests.post(url, json=data, timeout=30)
    print('✅ Статус:', response.status_code)
    print('📄 твет:', response.json())
except Exception as e:
    print('❌ шибка:', e)
