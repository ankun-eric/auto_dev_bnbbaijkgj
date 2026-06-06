#!/usr/bin/env python3
"""Comprehensive FastAPI route extractor that only includes routes from registered routers."""
import os, re, ast, sys
from collections import defaultdict

API_DIR = 'app/api'
MAIN_FILE = 'app/main.py'

def parse_main_includes():
    """Parse main.py and return list of (module_path, router_attr_name, line_no)."""
    included = []
    with open(MAIN_FILE, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    # Find all import blocks for app.api modules (from the big import block at top)
    imported_modules = {}
    # The main import block starts at line 12
    in_import = False
    for i, line in enumerate(lines, 1):
        if 'from app.api import (' in line:
            in_import = True
            continue
        if in_import:
            if ')' in line:
                in_import = False
                continue
            # Extract module name
            m = re.search(r'^\s*(\w+)', line.strip().rstrip(','))
            if m:
                mod_name = m.group(1)
                imported_modules[mod_name] = os.path.join(API_DIR, mod_name + '.py')
    
    # Also find import-as lines like "from app.api import xxx as _xxx"
    for i, line in enumerate(lines, 1):
        m = re.search(r'from app\.api import (\w+) as _(\w+)', line)
        if m:
            mod_name = m.group(1)
            alias = m.group(2)
            imported_modules[alias] = os.path.join(API_DIR, mod_name + '.py')
        
        # Also "from app.api import xxx" (single imports)
        m2 = re.search(r'^from app\.api import (\w+)\s*$', line.strip())
        if m2 and line.strip().startswith('from app.api import ') and ' as ' not in line:
            mod_name = m2.group(1)
            imported_modules[mod_name] = os.path.join(API_DIR, mod_name + '.py')
    
    # Find all include_router calls (skip comments)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        # Match: app.include_router(xxx.router) or app.include_router(xxx.admin_router) etc.
        m = re.search(r'app\.include_router\((\w+(?:\.\w+)*)\)', line)
        if m:
            ref = m.group(1)
            parts = ref.split('.')
            if len(parts) >= 2:
                mod_ref = parts[0]
                attr = '.'.join(parts[1:])
                # Resolve module file path
                if mod_ref in imported_modules:
                    included.append((imported_modules[mod_ref], attr, i))
                elif mod_ref.startswith('_'):
                    # try without leading underscore
                    real_mod = mod_ref[1:]
                    if real_mod in imported_modules:
                        included.append((imported_modules[real_mod], attr, i))
    
    # Direct @app.get/post etc in main.py
    for i, line in enumerate(lines, 1):
        m = re.search(r'@app\.(get|post|put|delete|patch)\s*\(\s*(["\'])([^"\']+)\2', line)
        if m:
            method = m.group(1).upper()
            path = m.group(3)
            included.append(('DIRECT_MAIN', method, path, i))
    
    # app.mount
    for i, line in enumerate(lines, 1):
        m = re.search(r'app\.mount\s*\(\s*(["\'])([^"\']+)\1', line)
        if m:
            included.append(('MOUNT', m.group(2), i))
    
    return included


def extract_routes_from_file(filepath, router_vars):
    """Extract routes from a file for specific router variables.
    
    Returns list of (method, full_path, line_no).
    """
    if not os.path.exists(filepath):
        return []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        lines = content.split('\n')
    
    # First, collect all simple string constants defined before usage
    # e.g. USER_PREFIX = "/api/home_safety"
    string_constants = {}
    for i, line in enumerate(lines, 1):
        m = re.search(r'(\w+)\s*=\s*(["\'])([^"\']+)\2', line)
        if m:
            string_constants[m.group(1)] = m.group(3)
    
    # Find APIRouter definitions and their prefixes
    router_info = {}  # var_name -> prefix
    for i, line in enumerate(lines, 1):
        m = re.search(r'(\w+)\s*=\s*APIRouter\s*\((.*)', line)
        if m:
            var_name = m.group(1)
            args_start = m.group(2)
            # Collect multiline args
            full_args = args_start
            if ')' not in args_start:
                for j in range(i, len(lines)):
                    full_args += '\n' + lines[j]
                    if ')' in lines[j]:
                        break
            pfx_m = re.search(r'prefix\s*=\s*(["\'])([^"\']+)\1', full_args)
            prefix = pfx_m.group(2) if pfx_m else ''
            router_info[var_name] = prefix
    
    def resolve_path(match_str):
        """Try to resolve a route path that may contain variable references.
        e.g. USER_PREFIX + "/devices" -> "/api/home_safety/devices"
        """
        # Try literal string first
        lit = re.search(r'^(["\'])([^"\']+)\1$', match_str.strip())
        if lit:
            return lit.group(2)
        # Try VAR + "suffix"
        concat = re.search(r'^(\w+)\s*\+\s*(["\'])([^"\']*)\2$', match_str.strip())
        if concat:
            var = concat.group(1)
            suffix = concat.group(3)
            if var in string_constants:
                return string_constants[var] + suffix
        # Try "prefix" + VAR
        concat2 = re.search(r'^(["\'])([^"\']*)\1\s*\+\s*(\w+)$', match_str.strip())
        if concat2:
            prefix_s = concat2.group(2)
            var2 = concat2.group(3)
            if var2 in string_constants:
                return prefix_s + string_constants[var2]
        # Try f-string (only simple ones)
        fstr = re.search(r'^f(["\'])([^"\']*)\1$', match_str.strip())
        if fstr:
            # Replace simple {var} with placeholder
            path = fstr.group(2)
            path = re.sub(r'\{(\w+)\}', r'{\1}', path)
            return path
        return None
    
    results = []
    for var_name in router_vars:
        if var_name not in router_info:
            continue
        prefix = router_info[var_name]
        
        # Find all route decorators for this variable
        for i, line in enumerate(lines, 1):
            # Pattern 1: @router.get("/path") - literal string
            m = re.search(r'@' + re.escape(var_name) + r'\.(get|post|put|delete|patch)\s*\(\s*(["\'])([^"\']+)\2', line)
            if m:
                method = m.group(1).upper()
                path = m.group(3)
                full_path = prefix + path if prefix else path
                results.append((method, full_path, i))
            else:
                # Pattern 2: @router.get(VAR + "/path") or @router.get("/path" + VAR) or @router.get(f"/path/{var}")
                m2 = re.search(r'@' + re.escape(var_name) + r'\.(get|post|put|delete|patch)\s*\((.+?)\)\s*$', line)
                if m2:
                    method = m2.group(1).upper()
                    arg = m2.group(2).strip()
                    path = resolve_path(arg)
                    if path:
                        full_path = prefix + path if prefix else path
                        results.append((method, full_path, i))
    
    return results


def main():
    includes = parse_main_includes()
    
    # Separate: (filepath, router_attr) tuples and direct routes
    router_registrations = []  # list of (filepath, [router_var_names])
    file_router_map = defaultdict(list)
    
    direct_routes = []
    mount_routes = []
    
    for item in includes:
        if len(item) == 4 and item[0] == 'DIRECT_MAIN':
            _, method, path, line_no = item
            direct_routes.append((method, path, MAIN_FILE, line_no))
        elif len(item) == 3 and item[0] == 'MOUNT':
            _, mount_path, line_no = item
            mount_routes.append(('MOUNT', mount_path, MAIN_FILE, line_no))
        elif len(item) == 3:
            filepath, attr, line_no = item
            file_router_map[filepath].append(attr)
    
    all_routes = []  # (method, path, filepath, line_no)
    
    for filepath, attrs in file_router_map.items():
        routes = extract_routes_from_file(filepath, attrs)
        for method, path, line_no in routes:
            all_routes.append((method, path, filepath.replace('\\', '/'), line_no))
    
    for method, path, filepath, line_no in direct_routes:
        all_routes.append((method, path, filepath, line_no))
    
    for method, path, filepath, line_no in mount_routes:
        all_routes.append((method, path, filepath, line_no))
    
    # Deduplicate by (method, path)
    seen = set()
    unique = []
    for r in all_routes:
        key = (r[0], r[1])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    # Sort: method order (GET, POST, PUT, PATCH, DELETE, MOUNT), then path alphabetically
    method_order = {'GET': 0, 'POST': 1, 'PUT': 2, 'PATCH': 3, 'DELETE': 4, 'MOUNT': 5}
    
    def sort_key(r):
        m = method_order.get(r[0], 99)
        return (m, r[1])
    
    unique.sort(key=sort_key)
    
    for method, path, filepath, line_no in unique:
        print(f'{method} {path} ← {filepath}:{line_no}')


if __name__ == '__main__':
    main()
