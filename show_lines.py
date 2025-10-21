lines = open(r'E:\ii-agent\backend\main.py', 'r', encoding='utf-8').readlines()
for i in range(220, 230):
    print(f'{i}: {repr(lines[i][:70])}')
