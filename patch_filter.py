import re
content = open(r'E:\ii-agent\backend\main.py', 'r', encoding='utf-8').read()
filter_func = '''
def filter_chinese_characters(text: str) -> str:
    if not text:
        return text
    chinese_ranges = [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x2A6DF)]
    filtered_chars = []
    for char in text:
        if not any(start <= ord(char) <= end for start, end in chinese_ranges):
            filtered_chars.append(char)
    return ''.join(filtered_chars)

'''
match = re.search(r'(def query_ollama\()', content)
content = content[:match.start()] + filter_func + '\n' + content[match.start():]
content = re.sub(r'(        response = query_ollama\(full_prompt, model=model\))', r'\1\n        if response:\n            response = filter_chinese_characters(response)', content, count=1)
open(r'E:\ii-agent\backend\main.py', 'w', encoding='utf-8').write(content)
print('Patch applied!')
