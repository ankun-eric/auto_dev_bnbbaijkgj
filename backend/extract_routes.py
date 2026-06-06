#!/usr/bin/env python3
"""Extract all FastAPI route definitions from the backend project."""
import os, re, sys

API_DIR = 'app/api'
MAIN_FILE = 'app/main.py'

def extract_routes():
    results = []
    
    # First collect all include_router calls from main.py
    include_routers = []
    with open(MAIN_FILE, 'r', encoding='utf-8', errors='replace') as f:
        main_content = f.read()
        main_lines = main_content.split('\n')
    
    # Also find @app.get directly in main.py
    for i, line in enumerate(main_lines, 1):
        m = re.search(r"@app\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", line)
        if m:
            method = m.group(1).upper()
            path = m.group(2)
            results.append((MAIN_FILE, i, method, path))
    
    # app.mount
    for i, line in enumerate(main_lines, 1):
        m = re.search(r"app\.mount\s*\(\s*['\"]([^'\"]+)['\"]", line)
        if m:
            results.append((MAIN_FILE, i, 'MOUNT', m.group(1)))
    
    # Now for each API file
    api_files = [f for f in os.listdir(API_DIR) if f.endswith('.py') and f != '__init__.py']
    
    for fname in api_files:
        fpath = os.path.join(API_DIR, fname)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Find all APIRouter() definitions - collect prefix per variable name
        router_prefixes = {}  # var_name -> prefix
        for i, line in enumerate(lines, 1):
            # Match: something = APIRouter(...)
            m = re.search(r'(\w+)\s*=\s*APIRouter\s*\((.*?)\)\s*$', line)
            if not m:
                # Try multiline - if line starts with var = APIRouter( and doesn't close
                m2 = re.search(r'(\w+)\s*=\s*APIRouter\s*\((.*)', line)
                if m2 and ')' not in m2.group(2):
                    # collect multiline
                    full_args = m2.group(2)
                    for j in range(i, len(lines)):
                        full_args += '\n' + lines[j]
                        if ')' in lines[j]:
                            break
                    var_name = m2.group(1)
                else:
                    continue
            else:
                var_name = m.group(1)
                full_args = m.group(2)
            
            pfx_m = re.search(r'prefix\s*=\s*["\']([^"\']+)["\']', full_args)
            prefix = pfx_m.group(1) if pfx_m else ''
            router_prefixes[var_name] = prefix
        
        # Find all route decorators
        for i, line in enumerate(lines, 1):
            # Match @something.method('/path'
            m = re.search(r'@(\w+)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', line)
            if m:
                var_name = m.group(1)
                method = m.group(2).upper()
                path = m.group(3)
                rpfx = router_prefixes.get(var_name, '')
                full_path = rpfx + path if rpfx else path
                results.append((fpath, i, method, full_path, rpfx, path, var_name))
    
    return results

if __name__ == '__main__':
    results = extract_routes()
    for r in sorted(results, key=lambda x: (x[2], x[3])):
        if len(r) == 4:
            fpath, line_no, method, path = r
            print(f'{method} {path} / {fpath}:{line_no}')
        elif len(r) == 7:
            fpath, line_no, method, full_path, rpfx, path, var_name = r
            print(f'{method} {full_path} / {fpath}:{line_no}')
