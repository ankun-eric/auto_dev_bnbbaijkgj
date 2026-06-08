import re
import os

api_dir = os.path.join(os.path.dirname(__file__), 'app', 'api')
main_path = os.path.join(os.path.dirname(__file__), 'app', 'main.py')

routes = []


def extract_routes_from_file(fpath, fname):
    """Extract all routes from a single Python file."""
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    
    # First pass: find all APIRouter definitions (single-line only)
    router_prefixes = {}
    for i, line in enumerate(lines):
        # Match: var = APIRouter(...)  where ... contains prefix="..."
        m = re.match(r'(\w+)\s*=\s*APIRouter\s*\(\s*.*?prefix\s*=\s*[\"\']([^\"\']+)[\"\']', line)
        if m:
            router_prefixes[m.group(1)] = m.group(2)
        # Also match APIRouter() without prefix
        m2 = re.match(r'(\w+)\s*=\s*APIRouter\s*\(\s*\)', line)
        if m2 and m2.group(1) not in router_prefixes:
            router_prefixes[m2.group(1)] = ''
        # Also match APIRouter(tags=...) without prefix
        m3 = re.match(r'(\w+)\s*=\s*APIRouter\s*\(\s*(?:tags|dependencies|responses|route_class)', line)
        if m3 and m3.group(1) not in router_prefixes:
            # Need to check if prefix is absent; do a negative check
            if 'prefix' not in line:
                router_prefixes[m3.group(1)] = ''
    
    # Second pass: find all route decorators
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        
        # Single-line: @var.method("/path", ...)
        m = re.match(r'\s*@(\w+)\.(get|post|put|delete|patch|head|options)\s*\(\s*[\"\']([^\"\']+)[\"\']', line)
        if m:
            var_name = m.group(1)
            method = m.group(2).upper()
            path = m.group(3)
            if var_name in router_prefixes or var_name == 'app':
                prefix = router_prefixes.get(var_name, '')
                full_path = prefix.rstrip('/') + '/' + path.lstrip('/')
                full_path = '/' + full_path.strip('/')
                result.append((method, full_path, f'{fname}:{lineno}'))
            i += 1
            continue
        
        # Multi-line start: @var.method(
        m2 = re.match(r'\s*@(\w+)\.(get|post|put|delete|patch|head|options)\s*\(\s*$', line)
        if m2:
            var_name = m2.group(1)
            method = m2.group(2).upper()
            # Look ahead for the path
            for j in range(i + 1, min(i + 5, len(lines))):
                pm = re.search(r'[\"\'](/[^\"\']*)[\"\']', lines[j])
                if pm:
                    path = pm.group(1)
                    if var_name in router_prefixes or var_name == 'app':
                        prefix = router_prefixes.get(var_name, '')
                        full_path = prefix.rstrip('/') + '/' + path.lstrip('/')
                        full_path = '/' + full_path.strip('/')
                        result.append((method, full_path, f'{fname}:{lineno}'))
                    break
            i += 1
            continue
        
        i += 1
    
    return result


# Step 1: Process all api/*.py files
for fname in sorted(os.listdir(api_dir)):
    if not fname.endswith('.py') or fname == '__init__.py':
        continue
    fpath = os.path.join(api_dir, fname)
    file_routes = extract_routes_from_file(fpath, fname)
    routes.extend(file_routes)

# Step 2: Process main.py
# main.py has @app.get("/api/health")
main_routes = extract_routes_from_file(main_path, 'main.py')
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
