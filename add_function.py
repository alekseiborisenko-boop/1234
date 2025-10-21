import re

with open(r"E:\ii-agent\backend\main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# аходим строку 336 (def detect_query_type)
insert_line = 336
# щем конец этой функции (следующая def или пустая строка на уровне 0 отступов)
for i in range(insert_line, len(lines)):
    if i > insert_line and lines[i].startswith("def "):
        insert_line = i
        break

# ставляем функцию
filter_code = """
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

lines.insert(insert_line, filter_code)

with open(r"E:\ii-agent\backend\main.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"✅ ункция добавлена перед строкой {insert_line}")
