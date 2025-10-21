content = open(r'E:\ii-agent\backend\main.py', 'r', encoding='utf-8').read()

# щем по уникальной строке  которой нужно вставить кэш
insert_before = "logger.info(f'🔍 Google CSE search: {query}')"
pos = content.find(insert_before)

if pos > 0:
    # айти начало строки (отступ)
    line_start = content.rfind('\n', 0, pos) + 1
    indent = ' ' * (pos - line_start)
    
    cache_check = f"""{indent}# Check cache first
{indent}cache_key = f"{{query}}_{{max_results}}"
{indent}cached_results = cache_manager.get(cache_key, 'google_cse')
{indent}if cached_results:
{indent}    logger.info(f'🎯 Cache HIT for Google CSE: {{query[:50]}}...')
{indent}    return cached_results

{indent}"""
    
    content = content[:line_start] + cache_check + content[line_start:]
    print(f'✅ Cache CHECK added at position {pos}')
    
    open(r'E:\ii-agent\backend\main.py', 'w', encoding='utf-8').write(content)
    print('✅ File saved!')
else:
    print('⚠️ Insert point not found')
