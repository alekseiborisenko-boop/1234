import re
import os
from pathlib import Path

# агрузить .env если есть
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f'Loaded .env from {env_path}')

content = open(r'E:\ii-agent\backend\main.py', 'r', encoding='utf-8').read()

# роверить есть ли уже load_dotenv
if 'load_dotenv' not in content:
    # обавить import в начало
    imports_section = content.split('# FastAPI')[0]
    new_import = 'from dotenv import load_dotenv\nimport os\nfrom pathlib import Path\n\n'
    content = new_import + content
    
    # обавить загрузку после импортов
    content = content.replace(
        'logger = logging.getLogger(__name__)',
        '''# Load environment variables
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f'✅ Loaded .env from {env_path}')
else:
    logger.warning('⚠️ .env file not found')

logger = logging.getLogger(__name__)'''
    )

# лучшить фильтр китайских символов
filter_func = '''
def filter_chinese_characters(text: str) -> str:
    if not text:
        return text
    # иапазоны для китайских символов  пунктуации
    chinese_ranges = [
        (0x4E00, 0x9FFF),   # сновные иероглифы
        (0x3400, 0x4DBF),   # асширение A
        (0x20000, 0x2A6DF), # асширение B
        (0x3000, 0x303F),   # итайская пунктуация
        (0xFF00, 0xFFEF)    # олноширинные символы
    ]
    filtered_chars = []
    for char in text:
        char_code = ord(char)
        is_chinese = any(start <= char_code <= end for start, end in chinese_ranges)
        if not is_chinese:
            filtered_chars.append(char)
    return ''.join(filtered_chars).strip()

'''

# аменить старую функцию
if 'def filter_chinese_characters' in content:
    pattern = r'def filter_chinese_characters\(.*?\n(?:.*?\n)*?    return.*?\n\n'
    content = re.sub(pattern, filter_func, content, flags=re.MULTILINE)

open(r'E:\ii-agent\backend\main.py', 'w', encoding='utf-8').write(content)
print('✅ Patch applied: .env loader + improved filter')
