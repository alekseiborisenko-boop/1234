import re

# Read main.py
main = open(r'E:\ii-agent\backend\main.py', 'r', encoding='utf-8').read()

# Find and update analyze endpoint
pattern = r'(@app\.post\("/ai-dev/analyze"\).*?async def analyze_ai_task\(request: Request\):.*?data = await request\.json\(\).*?task = data\.get\("task"\))'

replacement = '''@app.post("/ai-dev/analyze")
async def analyze_ai_task(request: Request):
    data = await request.json()
    task = data.get("task")
    provider = data.get("provider", "groq")'''

main = re.sub(pattern, replacement, main, flags=re.DOTALL)

# Update ai_developer call
main = re.sub(
    r'analysis = ai_developer\.analyze_task\(task\)',
    'analysis = ai_developer.analyze_task(task, provider)',
    main
)

# Save
open(r'E:\ii-agent\backend\main.py', 'w', encoding='utf-8').write(main)
print('✅ Main.py updated with provider parameter!')
