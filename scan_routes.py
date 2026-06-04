#!/usr/bin/env python3
"""Scan all API route endpoints from the backend project."""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_DIR = r'backend\app\api'
MAIN_FILE = r'backend\app\main.py'
BASE_DIR = os.getcwd()

# Output file
OUTPUT_FILE = r'route_list.txt'

prefix_map = {}  # (file_path, var_name) -> prefix
routes = []      # list of (method, full_path, file, line, var_name)

# ── Step 1: Find all APIRouter prefix definitions ──
def find_prefixes():
    for root, dirs, files in os.walk(API_DIR):
        for f in files:
            if not f.endswith('.py'):
                continue
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, BASE_DIR).replace('\\', '/')
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read()
            except Exception as e:
                print(f"ERROR reading {fpath}: {e}", file=sys.stderr)
                continue

            # Match patterns like:
            # router = APIRouter(prefix="/api/xxx")
            # admin_router = APIRouter(prefix="/api/admin/xxx")
            # public_router = APIRouter(prefix="/api/xxx")
            # etc.
            pattern = re.compile(
                r'(\w+)\s*=\s*APIRouter\s*\(\s*'
                r'(?:[^)]*?)'
                r'prefix\s*=\s*["\x27]([^\"\x27]+)["\x27]'
            )
            for m in pattern.finditer(content):
                var_name = m.group(1)
                prefix = m.group(2)
                key = (relpath, var_name)
                prefix_map[key] = prefix
                print(f"[PREFIX] {relpath} :: {var_name} = {prefix}")

    # Also check for APIRouter without prefix (default empty)
    for root, dirs, files in os.walk(API_DIR):
        for f in files:
            if not f.endswith('.py'):
                continue
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, BASE_DIR).replace('\\', '/')
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read()
            except:
                continue
            # Find all APIRouter()-created variables
            for m in re.finditer(r'(\w+)\s*=\s*APIRouter\s*\(', content):
                var_name = m.group(1)
                key = (relpath, var_name)
                if key not in prefix_map:
                    prefix_map[key] = ''
                    print(f"[PREFIX] {relpath} :: {var_name} = (no prefix)")

# ── Step 2: Find all route decorators ──
def find_routes():
    for root, dirs, files in os.walk(API_DIR):
        for f in files:
            if not f.endswith('.py'):
                continue
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, BASE_DIR).replace('\\', '/')
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    lines = fh.readlines()
            except:
                continue

            for i, line in enumerate(lines, 1):
                # Match @xxx_router.method("path") or @router.method("path")
                m = re.match(
                    r'\s*@(\w+_router|\w*router)\.(get|post|put|delete|patch)'
                    r'\s*\(\s*["\x27]([^\"\x27]+)["\x27]',
                    line
                )
                if m:
                    var_name = m.group(1)
                    method = m.group(2).upper()
                    path = m.group(3)
                    routes.append((method, path, relpath, i, var_name))
                    print(f"[ROUTE] {method} {path} <- {relpath}:{i} ({var_name})")
                else:
                    # Try without the _router suffix, just @variable.method("path")
                    m2 = re.match(
                        r'\s*@(\w+)\.(get|post|put|delete|patch)'
                        r'\s*\(\s*["\x27]([^\"\x27]+)["\x27]',
                        line
                    )
                    if m2:
                        var_name = m2.group(1)
                        method = m2.group(2).upper()
                        path = m2.group(3)
                        # Skip @app.xxx (handled separately), skip known non-router
                        if var_name in ('app', 'staticmethod', 'classmethod', 'property'):
                            continue
                        routes.append((method, path, relpath, i, var_name))
                        print(f"[ROUTE] {method} {path} <- {relpath}:{i} ({var_name})")

# ── Step 3: Find @app.xxx in main.py ──
def find_app_routes():
    fpath = os.path.join(BASE_DIR, MAIN_FILE)
    relpath = os.path.relpath(fpath, BASE_DIR).replace('\\', '/')
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
    except:
        return
    for i, line in enumerate(lines, 1):
        m = re.match(
            r'\s*@app\.(get|post|put|delete|patch)'
            r'\s*\(\s*["\x27]([^\"\x27]+)["\x27]',
            line
        )
        if m:
            method = m.group(1).upper()
            path = m.group(2)
            routes.append((method, path, relpath, i, 'app'))
            print(f"[ROUTE-APP] {method} {path} <- {relpath}:{i}")

find_prefixes()
find_routes()
find_app_routes()

# ── Step 4: Merge prefixes ──
def merge_prefix(file_path, var_name, route_path):
    key = (file_path, var_name)
    prefix = prefix_map.get(key, '')
    if prefix:
        # Avoid double slashes
        if prefix.endswith('/') and route_path.startswith('/'):
            full = prefix + route_path[1:]
        elif prefix.endswith('/') or route_path.startswith('/'):
            full = prefix + route_path
        else:
            full = prefix + '/' + route_path
        return full
    return route_path

results = []
for method, path, file_path, line_no, var_name in routes:
    full_path = merge_prefix(file_path, var_name, path)
    # Normalize: ensure starts with /
    if not full_path.startswith('/'):
        full_path = '/' + full_path
    results.append((method, full_path, file_path, line_no))

# Deduplicate by (method, full_path)
seen = set()
unique_results = []
for r in results:
    key = (r[0], r[1])
    if key not in seen:
        seen.add(key)
        unique_results.append(r)

# Sort: GET first, then others; within method, sort by path alphabetically
def sort_key(r):
    method_order = {'GET': 0, 'POST': 1, 'PUT': 2, 'DELETE': 3, 'PATCH': 4}
    return (method_order.get(r[0], 99), r[1])

unique_results.sort(key=sort_key)

# ── Write output ──
with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
    for method, full_path, file_path, line_no in unique_results:
        line = f"{method} {full_path} \u2190 {file_path}:{line_no}\n"
        out.write(line)

print(f"\nTotal routes found: {len(unique_results)}")
print(f"Written to {OUTPUT_FILE}")
