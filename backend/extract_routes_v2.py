import re
import os
import sys

api_dir = os.path.join(os.path.dirname(__file__), 'app', 'api')
main_path = os.path.join(os.path.dirname(__file__), 'app', 'main.py')

routes = []
HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options'}


def extract_routes_from_content(content, fname, prefix_map=None):
    """Extract routes from file content. If prefix_map is given, it maps
    variable names to prefix strings (from APIRouter definitions)."""
    if prefix_map is None:
        prefix_map = {}
    
    lines = content.split('\n')
    result = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        
        # Match single-line decorator: @var.method("/path")
        m = re.match(r'\s*@(\w+)\.(get|post|put|delete|patch|head|options)\s*\(\s*[\"\']([^\"\']+)[\"\']', line)
        if m:
            var_name = m.group(1)
            method = m.group(2).upper()
            path = m.group(3)
            if var_name in prefix_map or var_name == 'app':
                prefix = prefix_map.get(var_name, '')
                full_path = prefix.rstrip('/') + '/' + path.lstrip('/')
                full_path = '/' + full_path.strip('/')
                result.append((method, full_path, f'{fname}:{lineno}'))
            i += 1
            continue
        
        # Match multi-line decorator start: @var.method(
        m2 = re.match(r'\s*@(\w+)\.(get|post|put|delete|patch|head|options)\s*\(', line)
        if m2:
            var_name = m2.group(1)
            method = m2.group(2).upper()
            # Look ahead for the path string
            combined = line
            j = i + 1
            found_path = None
            while j < len(lines) and j <= i + 5:  # Look up to 5 lines ahead
                combined += ' ' + lines[j]
                pm = re.search(r'[\"\'](/[^\"\']*)[\"\']', lines[j])
                if pm:
                    found_path = pm.group(1)
                    break
                j += 1
            
            if found_path and (var_name in prefix_map or var_name == 'app'):
                prefix = prefix_map.get(var_name, '')
                full_path = prefix.rstrip('/') + '/' + found_path.lstrip('/')
                full_path = '/' + full_path.strip('/')
                result.append((method, full_path, f'{fname}:{lineno}'))
            i += 1
            continue
        
        i += 1
    
    return result


# Step 1: Scan all api/*.py files
for fname in sorted(os.listdir(api_dir)):
    if not fname.endswith('.py') or fname == '__init__.py':
        continue
    fpath = os.path.join(api_dir, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all APIRouter definitions with prefix (handle multi-line)
    router_prefixes = {}
    lines = content.split('\n')
    for i, line in enumerate(lines):
        # Match: var = APIRouter(prefix="/xxx", ...)
        # Could be multi-line, but prefix is usually on the first line
        m = re.match(r'(\w+)\s*=\s*APIRouter\s*\(', line)
        if m:
            var_name = m.group(1)
            # Search for prefix in this line and next few lines
            combined = line
            for j in range(i, min(i+5, len(lines))):
                if j > i:
                    combined += ' ' + lines[j]
            pm = re.search(r'prefix\s*=\s*[\"\']([^\"\']+)[\"\']', combined)
            if pm:
                router_prefixes[var_name] = pm.group(1)
    
    # Extract routes
    file_routes = extract_routes_from_content(content, fname, router_prefixes)
    routes.extend(file_routes)

# Step 2: Extract @app.get etc. from main.py
with open(main_path, 'r', encoding='utf-8') as f:
    main_content = f.read()
main_routes = extract_routes_from_content(main_content, 'main.py', {'app': ''})
routes.extend(main_routes)

# Dedup and sort
seen = set()
unique = []
for method, path, loc in routes:
    key = (method, path)
    if key not in seen:
        seen.add(key)
        unique.append((method, path, loc))

# Sort: GET first, then POST, PUT, PATCH, DELETE, HEAD, OPTIONS
method_order = {'GET': 0, 'POST': 1, 'PUT': 2, 'PATCH': 3, 'DELETE': 4, 'HEAD': 5, 'OPTIONS': 6}
unique.sort(key=lambda x: (method_order.get(x[0], 99), x[1]))

for method, path, loc in unique:
    print(f'{method} {path} ← {loc}')
