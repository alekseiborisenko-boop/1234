import re

# итаем main.py
with open(r"E:\ii-agent\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. обавляем функцию filter_chinese_characters после detect_query_type
filter_func = """

# ильтр китайских символов
def filter_chinese_characters(text: str) -> str:
    if not text:
        return text
    chinese_ranges = [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x2A6DF), (0x2A700, 0x2B73F), (0x2B740, 0x2B81F), (0x2B820, 0x2CEAF), (0xF900, 0xFAFF), (0x3300, 0x33FF), (0xFE30, 0xFE4F), (0x2F800, 0x2FA1F)]
    filtered_chars = []
    removed_count = 0
    for char in text:
        char_code = ord(char)
        is_chinese = any(start <= char_code <= end for start, end in chinese_ranges)
        if not is_chinese:
            filtered_chars.append(char)
        else:
            removed_count += 1
    filtered_text = ''.join(filtered_chars)
    if removed_count > 0:
        logger.warning(f"Removed {removed_count} Chinese characters from response")
    return filtered_text
"""

# аходим конец функции detect_query_type
pattern = r'(def detect_query_type\(query\):.*?return query_type)'
match = re.search(pattern, content, re.DOTALL)
if match:
    insert_pos = match.end()
    content = content[:insert_pos] + filter_func + content[insert_pos:]
    print("✅ ункция filter_chinese_characters добавлена")
else:
    print("❌ е найдена функция detect_query_type")

# 2. обавляем вызов фильтра после query_ollama
pattern = r'(        response = query_ollama\(full_prompt, model=model\))'
replacement = r'\1\n\n        # ильтрация китайских символов\n        if response:\n            response = filter_chinese_characters(response)'
content = re.sub(pattern, replacement, content)
print("✅ ильтр добавлен в /chat endpoint")

# Сохраняем
with open(r"E:\ii-agent\backend\main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ атч успешно применен!")
