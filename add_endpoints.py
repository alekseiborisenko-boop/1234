# обавление AI Developer API endpoints в main.py

content = open(r'E:\ii-agent\backend\main.py', 'r', encoding='utf-8').read()

# айти место для вставки (после последнего @app endpoint)
insert_marker = 'if __name__ == "__main__":'
insert_pos = content.rfind(insert_marker)

if insert_pos == -1:
    print('Marker not found!')
else:
    new_endpoints = '''
# ==================== AI DEVELOPER API ====================
from ai_developer import AIDeveloper

ai_dev = AIDeveloper()

@app.post("/ai-dev/analyze")
async def ai_dev_analyze(request: Request):
    """нализ задачи AI-разработчиком"""
    try:
        data = await request.json()
        task = data.get('task', '')
        
        if not task:
            return JSONResponse({'error': 'Task is required'}, status_code=400)
        
        analysis = ai_dev.analyze_task(task)
        return JSONResponse({'success': True, 'analysis': analysis})
    except Exception as e:
        logger.error(f'AI Dev analyze error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/backup")
async def ai_dev_backup(request: Request):
    """Создание бэкапа файлов"""
    try:
        data = await request.json()
        files = data.get('files', [])
        task = data.get('task', 'Manual backup')
        
        backup_id = ai_dev.create_backup(files, task)
        return JSONResponse({'success': True, 'backup_id': backup_id})
    except Exception as e:
        logger.error(f'AI Dev backup error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/generate")
async def ai_dev_generate(request: Request):
    """енерация решения"""
    try:
        data = await request.json()
        task = data.get('task', '')
        file_path = data.get('file_path', '')
        current_code = data.get('current_code', '')
        
        solution = ai_dev.generate_solution(task, file_path, current_code)
        return JSONResponse({'success': True, 'solution': solution})
    except Exception as e:
        logger.error(f'AI Dev generate error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/apply")
async def ai_dev_apply(request: Request):
    """рименить изменения"""
    try:
        data = await request.json()
        file_path = data.get('file_path', '')
        new_code = data.get('new_code', '')
        
        success = ai_dev.apply_changes(file_path, new_code)
        return JSONResponse({'success': success})
    except Exception as e:
        logger.error(f'AI Dev apply error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/rollback")
async def ai_dev_rollback(request: Request):
    """ткат изменений"""
    try:
        data = await request.json()
        backup_id = data.get('backup_id', '')
        
        success = ai_dev.rollback(backup_id)
        return JSONResponse({'success': success})
    except Exception as e:
        logger.error(f'AI Dev rollback error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.get("/ai-dev/backups")
async def ai_dev_list_backups():
    """Список бэкапов"""
    try:
        backups = ai_dev.list_backups()
        return JSONResponse({'success': True, 'backups': backups})
    except Exception as e:
        logger.error(f'AI Dev list backups error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.get("/ai-dev/diff/{backup_id}")
async def ai_dev_get_diff(backup_id: str, file_path: str):
    """олучить diff"""
    try:
        diff = ai_dev.get_diff(file_path, backup_id)
        return JSONResponse({'success': True, 'diff': diff})
    except Exception as e:
        logger.error(f'AI Dev diff error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

'''
    
    # ставить перед if __name__
    content = content[:insert_pos] + new_endpoints + '\n' + content[insert_pos:]
    
    open(r'E:\ii-agent\backend\main.py', 'w', encoding='utf-8').write(content)
    print('✅ API endpoints added to main.py')
    print(f'✅ Inserted at position: {insert_pos}')
