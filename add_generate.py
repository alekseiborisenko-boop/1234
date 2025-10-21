import re

main_path = r'E:\ii-agent\backend\main.py'

with open(main_path, 'r', encoding='utf-8') as f:
    code = f.read()

if '/ai-developer/generate' not in code:
    insert_point = code.find('@app.post("/ai-dev/analyze")')
    
    if insert_point != -1:
        next_decorator = code.find('@app.', insert_point + 100)
        
        new_endpoint = """
@app.post("/ai-developer/generate")
async def ai_dev_generate_solution(request: dict):
    \"\"\"енерация решения на основе анализа\"\"\"
    try:
        task = request.get('task', '')
        analysis = request.get('analysis', {})
        provider = request.get('provider', 'ollama')
        
        logger.info(f'🔄 Generating solution for: {task[:50]}...')
        
        if provider == 'ollama':
            response = await ollama_generate(
                model='qwen2.5-coder:7b',
                prompt=f'адача: {task}\n\nнализ: {analysis}\n\nСоздай подробное решение с кодом и пояснениями.'
            )
            solution = response.get('response', 'ешение не сгенерировано')
        else:
            import requests
            groq_key = os.getenv('GROQ_API_KEY')
            resp = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {groq_key}', 'Content-Type': 'application/json'},
                json={'model': 'llama-3.1-8b-instant', 'messages': [{'role': 'user', 'content': f'адача: {task}\n\nСоздай подробное решение.'}]}
            )
            solution = resp.json()['choices'][0]['message']['content']
        
        return {'success': True, 'solution': {'code': solution, 'explanation': 'ешение сгенерировано', 'files': []}}
    except Exception as e:
        logger.error(f'❌ Generate error: {e}')
        return {'success': False, 'error': str(e)}

"""
        
        code = code[:next_decorator] + new_endpoint + code[next_decorator:]
        
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        print('✅ Endpoint /ai-developer/generate добавлен!')
    else:
        print('⚠️ е найдена точка вставки')
else:
    print('✅ Endpoint уже существует')
