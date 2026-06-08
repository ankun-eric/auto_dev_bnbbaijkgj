import re
import os
import sys

api_dir = os.path.join(os.path.dirname(__file__), 'app', 'api')
main_path = os.path.join(os.path.dirname(__file__), 'app', 'main.py')

routes = []

# Step 1: Scan all api/*.py files
for fname in sorted(os.listdir(api_dir)):
    if not fname.endswith('.py') or fname == '__init__.py':
        continue
    fpath = os.path.join(api_dir, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
        flines = content.split('\n')
    
    # Find all APIRouter definitions with prefix
    router_prefixes = {}
    for i, line in enumerate(flines, 1):
        m = re.match(r'(\w+)\s*=\s*APIRouter\s*\(\s*.*?prefix\s*=\s*[\"\']([^\"\']+)[\"\']', line)
        if m:
            var_name = m.group(1)
            prefix = m.group(2)
            router_prefixes[var_name] = prefix
    
    if not router_prefixes:
        continue
    
    # Find route decorators
    for i, line in enumerate(flines, 1):
        m = re.match(r'\s*@(\w+)\.(get|post|put|delete|patch|head|options)\s*\(\s*[\"\']([^\"\']+)[\"\']', line)
        if m:
            var_name = m.group(1)
            method = m.group(2).upper()
            path = m.group(3)
            if var_name in router_prefixes:
                prefix = router_prefixes[var_name]
                full_path = prefix.rstrip('/') + '/' + path.lstrip('/')
                full_path = '/' + full_path.strip('/')
                routes.append((method, full_path, f'{fname}:{i}'))

# Step 2: Extract @app.get etc. from main.py
with open(main_path, 'r', encoding='utf-8') as f:
    main_lines = f.readlines()
for i, line in enumerate(main_lines, 1):
    m = re.match(r'\s*@app\.(get|post|put|delete|patch|head|options)\s*\(\s*[\"\']([^\"\']+)[\"\']', line)
    if m:
        method = m.group(1).upper()
        path = m.group(2)
        routes.append((method, path, f'main.py:{i}'))

# Dedup and sort
seen = set()
unique = []
for method, path, loc in routes:
    key = (method, path)
    if key not in seen:
        seen.add(key)
        unique.append((method, path, loc))

unique.sort(key=lambda x: (x[0], x[1]))

for method, path, loc in unique:
    print(f'{method} {path} ← {loc}')
