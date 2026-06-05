#!/usr/bin/env python3
"""Scan all routes from backend, admin-web, and h5-web projects."""
import os
import re
import json
import sys

BASE = r"C:\auto_output\bnbbaijkgj"

# ─── Backend route scanning ───
def scan_backend_routes():
    """Scan all FastAPI router files for route decorators."""
    api_dir = os.path.join(BASE, "backend", "app", "api")
    if not os.path.isdir(api_dir):
        print("[WARN] backend/api directory not found")
        return []
    
    routes = []
    # Read main.py for include_router prefixes
    main_py = os.path.join(BASE, "backend", "app", "main.py")
    
    py_files = sorted([
        f for f in os.listdir(api_dir)
        if f.endswith(".py") and f != "__init__.py"
    ])
    
    for py_file in py_files:
        fpath = os.path.join(api_dir, py_file)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        
        # Find all @router.{method}("path",...) or @router.{method}("/path",...)
        # Also @app.{method} for main.py
        patterns = [
            (r'@router\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']', False),
            (r'@router\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']', False),
        ]
        
        for pattern, _ in patterns:
            for m in re.finditer(pattern, content, re.IGNORECASE):
                method = m.group(1).upper()
                path = m.group(2)
                line_no = content[:m.start()].count("\n") + 1
                rel_path = os.path.relpath(fpath, BASE).replace("\\", "/")
                routes.append({
                    "method": method,
                    "path": path,
                    "file": rel_path,
                    "line": line_no,
                    "type": "API"
                })
    
    # Also check main.py for @app routes
    try:
        with open(main_py, "r", encoding="utf-8") as f:
            main_content = f.read()
    except Exception:
        main_content = ""
    
    for m in re.finditer(r'@app\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']', main_content, re.IGNORECASE):
        method = m.group(1).upper()
        path = m.group(2)
        line_no = main_content[:m.start()].count("\n") + 1
        routes.append({
            "method": method,
            "path": path,
            "file": "backend/app/main.py",
            "line": line_no,
            "type": "API"
        })
    
    # Deduplicate by (method, path)
    seen = set()
    unique = []
    for r in routes:
        key = (r["method"], r["path"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    unique.sort(key=lambda x: (x["path"], x["method"]))
    return unique


def scan_nextjs_routes(src_dir, prefix_label):
    """Scan Next.js App Router directory structure for page routes."""
    app_dir = os.path.join(BASE, src_dir, "src", "app")
    if not os.path.isdir(app_dir):
        print(f"[WARN] {app_dir} not found")
        return []
    
    routes = []
    
    for root, dirs, files in os.walk(app_dir):
        # Skip node_modules and hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules" and not d.startswith("_")]
        
        for fname in files:
            if fname in ("page.tsx", "page.js", "page.jsx"):
                fpath = os.path.join(root, fname)
                rel_dir = os.path.relpath(root, app_dir).replace("\\", "/")
                if rel_dir == ".":
                    route_path = "/"
                else:
                    # Convert directory structure to route path
                    # Handle route groups (xxx) - they don't appear in URL
                    # Handle dynamic segments [xxx]
                    parts = rel_dir.split("/")
                    route_parts = []
                    for p in parts:
                        if p.startswith("(") and p.endswith(")"):
                            continue  # Route group, not part of URL
                        route_parts.append(p)
                    route_path = "/" + "/".join(route_parts)
                
                rel_path = os.path.relpath(fpath, BASE).replace("\\", "/")
                routes.append({
                    "method": "GET",
                    "path": route_path,
                    "file": rel_path,
                    "line": 1,
                    "type": "PAGE"
                })
    
    # Deduplicate
    seen = set()
    unique = []
    for r in routes:
        if r["path"] not in seen:
            seen.add(r["path"])
            unique.append(r)
    
    unique.sort(key=lambda x: x["path"])
    return unique


# ─── Main ───
print("Scanning backend routes...", flush=True)
backend_routes = scan_backend_routes()
print(f"  Found {len(backend_routes)} backend API routes", flush=True)

print("Scanning admin-web routes...", flush=True)
admin_routes = scan_nextjs_routes("admin-web", "admin")
print(f"  Found {len(admin_routes)} admin page routes", flush=True)

print("Scanning h5-web routes...", flush=True)
h5_routes = scan_nextjs_routes("h5-web", "h5")
print(f"  Found {len(h5_routes)} h5 page routes", flush=True)

all_routes = {
    "backend": backend_routes,
    "admin": admin_routes,
    "h5": h5_routes,
    "total": len(backend_routes) + len(admin_routes) + len(h5_routes)
}

out_path = os.path.join(BASE, "scanned_routes.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(all_routes, f, indent=2, ensure_ascii=False)

print(f"\nTotal routes: {all_routes['total']}")
print(f"Written to: {out_path}")
