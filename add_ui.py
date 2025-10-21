# обавление UI для AI Developer в index.html

content = open(r'E:\ii-agent\frontend\index.html', 'r', encoding='utf-8').read()

# айти место для вставки (перед закрывающим </body>)
insert_marker = '</body>'
insert_pos = content.rfind(insert_marker)

if insert_pos == -1:
    print('❌ Marker </body> not found!')
else:
    ui_code = '''
    <!-- AI DEVELOPER TAB -->
    <div id=\"ai-dev-tab\" class=\"tab-content\" style=\"display:none;\">
        <h2>🤖 AI Developer</h2>
        
        <div class=\"ai-dev-container\">
            <div class=\"task-input\">
                <h3>адача для AI:</h3>
                <textarea id=\"ai-task-input\" rows=\"4\" style=\"width:100%; padding:10px; border-radius:5px; border:1px solid #444; background:#1a1a1a; color:#fff;\">обавь логирование в функцию analyze_task</textarea>
                <button onclick=\"analyzeTask()\" style=\"margin-top:10px; padding:10px 20px; background:#4CAF50; color:white; border:none; border-radius:5px; cursor:pointer;\">🔍 нализировать задачу</button>
            </div>
            
            <div id=\"ai-analysis\" style=\"margin-top:20px; display:none;\">
                <h3>📋 нализ:</h3>
                <div id=\"analysis-result\" style=\"background:#1a1a1a; padding:15px; border-radius:5px; border:1px solid #444;\"></div>
                <button onclick=\"generateSolution()\" style=\"margin-top:10px; padding:10px 20px; background:#2196F3; color:white; border:none; border-radius:5px; cursor:pointer;\">🤖 Сгенерировать решение</button>
            </div>
            
            <div id=\"ai-solution\" style=\"margin-top:20px; display:none;\">
                <h3>💡 редложенное решение:</h3>
                <div id=\"solution-explanation\" style=\"background:#1a1a1a; padding:15px; border-radius:5px; border:1px solid #444; margin-bottom:10px;\"></div>
                <pre id=\"solution-code\" style=\"background:#000; padding:15px; border-radius:5px; overflow-x:auto; max-height:400px;\"></pre>
                <div style=\"margin-top:10px;\">
                    <button onclick=\"applySolution()\" style=\"padding:10px 20px; background:#4CAF50; color:white; border:none; border-radius:5px; cursor:pointer; margin-right:10px;\">✅ рименить</button>
                    <button onclick=\"rejectSolution()\" style=\"padding:10px 20px; background:#f44336; color:white; border:none; border-radius:5px; cursor:pointer;\">❌ тклонить</button>
                </div>
            </div>
            
            <div id=\"ai-backups\" style=\"margin-top:30px;\">
                <h3>📜 стория бэкапов:</h3>
                <button onclick=\"loadBackups()\" style=\"padding:8px 15px; background:#555; color:white; border:none; border-radius:5px; cursor:pointer;\">🔄 бновить</button>
                <div id=\"backups-list\" style=\"margin-top:10px;\"></div>
            </div>
        </div>
    </div>
    
    <script>
    let currentAnalysis = null;
    let currentSolution = null;
    
    async function analyzeTask() {
        const task = document.getElementById('ai-task-input').value;
        if (!task) return alert('ведите задачу');
        
        try {
            const response = await fetch('http://localhost:8000/ai-dev/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task})
            });
            
            const data = await response.json();
            if (data.success) {
                currentAnalysis = data.analysis;
                displayAnalysis(data.analysis);
            } else {
                alert('шибка анализа: ' + data.error);
            }
        } catch (e) {
            alert('шибка: ' + e.message);
        }
    }
    
    function displayAnalysis(analysis) {
        const html = 
            <p><strong>Сложность:</strong> </p>
            <p><strong>айлы для изменения:</strong> </p>
            <p><strong>овые файлы:</strong> </p>
            <p><strong>лан:</strong></p>
            <ol></ol>
        ;
        document.getElementById('analysis-result').innerHTML = html;
        document.getElementById('ai-analysis').style.display = 'block';
    }
    
    async function generateSolution() {
        if (!currentAnalysis) return;
        
        const files = [...currentAnalysis.files_to_modify, ...currentAnalysis.files_to_create];
        if (files.length === 0) return alert('ет файлов для обработки');
        
        const task = document.getElementById('ai-task-input').value;
        const file_path = files[0]; // ерём первый файл
        
        try {
            const response = await fetch('http://localhost:8000/ai-dev/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task, file_path, current_code: ''})
            });
            
            const data = await response.json();
            if (data.success) {
                currentSolution = {file_path, ...data.solution};
                displaySolution(currentSolution);
            } else {
                alert('шибка генерации: ' + data.error);
            }
        } catch (e) {
            alert('шибка: ' + e.message);
        }
    }
    
    function displaySolution(solution) {
        document.getElementById('solution-explanation').innerHTML = 
            <p><strong>айл:</strong> </p>
            <p><strong>бъяснение:</strong> </p>
            <p><strong>зменения:</strong> </p>
        ;
        document.getElementById('solution-code').textContent = solution.code;
        document.getElementById('ai-solution').style.display = 'block';
    }
    
    async function applySolution() {
        if (!currentSolution) return;
        
        if (!confirm('рименить изменения? удет создан бэкап.')) return;
        
        // Создать бэкап
        await fetch('http://localhost:8000/ai-dev/backup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                files: [currentSolution.file_path],
                task: document.getElementById('ai-task-input').value
            })
        });
        
        // рименить изменения
        const response = await fetch('http://localhost:8000/ai-dev/apply', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                file_path: currentSolution.file_path,
                new_code: currentSolution.code
            })
        });
        
        const data = await response.json();
        if (data.success) {
            alert('✅ зменения применены!');
            loadBackups();
        } else {
            alert('❌ шибка: ' + data.error);
        }
    }
    
    function rejectSolution() {
        document.getElementById('ai-solution').style.display = 'none';
        currentSolution = null;
    }
    
    async function loadBackups() {
        try {
            const response = await fetch('http://localhost:8000/ai-dev/backups');
            const data = await response.json();
            
            if (data.success) {
                const html = data.backups.map(backup => 
                    <div style=\"background:#1a1a1a; padding:10px; margin:5px 0; border-radius:5px; border:1px solid #444;\">
                        <strong></strong> - <br>
                        <small>айлов: </small>
                        <button onclick=\"rollbackBackup('')\" style=\"float:right; padding:5px 10px; background:#ff9800; color:white; border:none; border-radius:3px; cursor:pointer;\">↩️ ткатить</button>
                    </div>
                ).join('');
                document.getElementById('backups-list').innerHTML = html || '<p>ет бэкапов</p>';
            }
        } catch (e) {
            console.error('Load backups error:', e);
        }
    }
    
    async function rollbackBackup(backupId) {
        if (!confirm('ткатить изменения из бэкапа ' + backupId + '?')) return;
        
        const response = await fetch('http://localhost:8000/ai-dev/rollback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({backup_id: backupId})
        });
        
        const data = await response.json();
        if (data.success) {
            alert('✅ ткат выполнен!');
            loadBackups();
        } else {
            alert('❌ шибка: ' + data.error);
        }
    }
    
    // обавить кнопку в навигацию
    document.addEventListener('DOMContentLoaded', () => {
        const nav = document.querySelector('.tab-nav');
        if (nav) {
            const aiDevBtn = document.createElement('button');
            aiDevBtn.textContent = '🤖 AI Dev';
            aiDevBtn.className = 'tab-btn';
            aiDevBtn.onclick = () => {
                document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
                document.getElementById('ai-dev-tab').style.display = 'block';
                loadBackups();
            };
            nav.appendChild(aiDevBtn);
        }
    });
    </script>
'''
    
    # ставить перед </body>
    content = content[:insert_pos] + ui_code + '\n' + content[insert_pos:]
    
    open(r'E:\ii-agent\frontend\index.html', 'w', encoding='utf-8').write(content)
    print('✅ UI added to index.html')
    print(f'✅ Inserted at position: {insert_pos}')
