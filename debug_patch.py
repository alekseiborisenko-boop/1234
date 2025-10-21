# Временный патч для отладки
import sys
sys.path.insert(0, '/app')

original_post = __import__('requests').post

def debug_post(url, *args, **kwargs):
    if 'api/generate' in url:
        print(f"🔍 DEBUG: POST {url}")
        print(f"🔍 DEBUG: JSON={kwargs.get('json', {})}")
    result = original_post(url, *args, **kwargs)
    if 'api/generate' in url:
        print(f"🔍 DEBUG: Status={result.status_code}")
    return result

__import__('requests').post = debug_post
