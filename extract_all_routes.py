"""
全量路由提取脚本：从后端 (FastAPI) 和前端 (Next.js App Router) 提取所有路由。
输出 JSON 文件: all_routes_extracted.json
"""
import re
import os
import json
import ast
from pathlib import Path

BASE_DIR = Path(r"C:\auto_output\bnbbaijkgj")
BACKEND_API = BASE_DIR / "backend" / "app" / "api"
BACKEND_MAIN = BASE_DIR / "backend" / "app" / "main.py"
H5_SRC = BASE_DIR / "h5-web" / "src" / "app"
ADMIN_SRC = BASE_DIR / "admin-web" / "src" / "app"

OUTPUT = BASE_DIR / "all_routes_extracted.json"

results = {
    "backend_routes": [],
    "h5_routes": [],
    "admin_routes": [],
    "backend_stats": {},
    "h5_stats": {},
    "admin_stats": {},
}

# ── 1. 后端路由提取 ──
# 从所有 API 文件中提取 @router.get/post/put/delete/patch 装饰器
# 以及 router.prefix

backend_route_pattern = re.compile(
    r"""@(router|public_protocol_router|admin_router|user_router|settings_router|
       audit_phone_router|audit_router|partner_router|new_user_router|
       staff_router|order_card_router|product_card_router|poster_router|
       admin_router|public_router|_med_plan_alias_router|
       goods_tags_router|recommend_router|admin_router)
       \.(get|post|put|delete|patch|options|head)\s*\(\s*["']([^\"']+)""",
    re.VERBOSE | re.IGNORECASE
)

router_prefix_pattern = re.compile(
    r"""router\s*=\s*APIRouter\s*\([^)]*prefix\s*=\s*["']([^\"']+)""",
    re.IGNORECASE
)

# Also handle @app.get etc in main.py
app_route_pattern = re.compile(
    r"""@app\.(get|post|put|delete|patch)\s*\(\s*["']([^\"']+)""",
    re.IGNORECASE
)

api_files = sorted(BACKEND_API.glob("*.py"))
all_backend_routes = []

for fpath in api_files:
    if fpath.name == "__init__.py":
        continue
    try:
        content = fpath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue

    # Find router prefix
    prefix = ""
    prefix_match = router_prefix_pattern.search(content)
    if prefix_match:
        prefix = prefix_match.group(1)

    # Find route decorators
    for m in backend_route_pattern.finditer(content):
        method = m.group(2).upper()
        path = m.group(3)
        full_path = (prefix + path).replace("//", "/")
        if not full_path.startswith("/"):
            full_path = "/" + full_path
        all_backend_routes.append({
            "method": method,
            "path": full_path,
            "file": str(fpath.relative_to(BASE_DIR)),
            "prefix": prefix,
        })

# Also extract from main.py
try:
    main_content = BACKEND_MAIN.read_text(encoding="utf-8", errors="replace")
    for m in app_route_pattern.finditer(main_content):
        method = m.group(1).upper()
        path = m.group(2)
        all_backend_routes.append({
            "method": method,
            "path": path,
            "file": "backend/app/main.py",
            "prefix": "",
        })
except Exception:
    pass

# Deduplicate backend routes (same path+method)
seen = set()
deduped_backend = []
for r in all_backend_routes:
    key = (r["path"], r["method"])
    if key not in seen:
        seen.add(key)
        deduped_backend.append(r)

results["backend_routes"] = sorted(deduped_backend, key=lambda x: (x["path"], x["method"]))
results["backend_stats"] = {
    "total_files": len([f for f in api_files if f.name != "__init__.py"]),
    "total_routes": len(deduped_backend),
    "by_method": {},
    "by_prefix": {},
}
for r in deduped_backend:
    m = r["method"]
    results["backend_stats"]["by_method"][m] = results["backend_stats"]["by_method"].get(m, 0) + 1
    # Group by first path segment
    seg = r["path"].split("/")[1] if len(r["path"].split("/")) > 1 else "/"
    prefix_key = "/" + seg
    results["backend_stats"]["by_prefix"][prefix_key] = results["backend_stats"]["by_prefix"].get(prefix_key, 0) + 1


# ── 2. H5 前端路由提取 (Next.js App Router) ──
# 从 src/app 下的 page.tsx / layout.tsx 推导路由
def extract_next_routes(src_dir: Path) -> list:
    """从 Next.js App Router 目录提取路由路径"""
    routes = []
    for root, dirs, files in os.walk(str(src_dir)):
        for f in files:
            if f in ("page.tsx", "page.ts", "layout.tsx", "layout.ts"):
                rel = Path(root).relative_to(src_dir)
                # Build URL path from directory structure
                path_segments = []
                for part in rel.parts:
                    # Handle route groups (xxx)
                    if part.startswith("(") and part.endswith(")"):
                        continue
                    # Handle dynamic segments [xxx]
                    if part.startswith("[") and part.endswith("]"):
                        path_segments.append(f"[{part[1:-1]}]")
                    else:
                        path_segments.append(part)
                path = "/" + "/".join(path_segments) if path_segments else "/"
                # Normalize
                path = path.replace("//", "/") or "/"
                file_type = "page" if f.startswith("page") else "layout"
                routes.append({
                    "path": path,
                    "type": file_type,
                    "file": str(Path(root, f).relative_to(src_dir.parent.parent)),
                })
    return routes

h5_routes_raw = extract_next_routes(H5_SRC)
admin_routes_raw = extract_next_routes(ADMIN_SRC)

# Deduplicate by path
seen_h5 = set()
h5_routes = []
for r in h5_routes_raw:
    if r["path"] not in seen_h5:
        seen_h5.add(r["path"])
        h5_routes.append(r)

seen_admin = set()
admin_routes = []
for r in admin_routes_raw:
    if r["path"] not in seen_admin:
        seen_admin.add(r["path"])
        admin_routes.append(r)

results["h5_routes"] = sorted(h5_routes, key=lambda x: x["path"])
results["h5_stats"] = {
    "total_routes": len(h5_routes),
    "total_pages": sum(1 for r in h5_routes if r["type"] == "page"),
    "total_layouts": sum(1 for r in h5_routes if r["type"] == "layout"),
}

results["admin_routes"] = sorted(admin_routes, key=lambda x: x["path"])
results["admin_stats"] = {
    "total_routes": len(admin_routes),
    "total_pages": sum(1 for r in admin_routes if r["type"] == "page"),
    "total_layouts": sum(1 for r in admin_routes if r["type"] == "layout"),
}

# Write output
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Backend routes: {results['backend_stats']['total_routes']}")
print(f"H5 frontend routes: {results['h5_stats']['total_routes']}")
print(f"Admin frontend routes: {results['admin_stats']['total_routes']}")
print(f"Output: {OUTPUT}")

# Also print a summary
print("\n--- Backend Routes by method ---")
for k, v in sorted(results["backend_stats"]["by_method"].items()):
    print(f"  {k}: {v}")

print("\n--- Backend Routes by prefix (top 20) ---")
for k, v in sorted(results["backend_stats"]["by_prefix"].items(), key=lambda x: -x[1])[:20]:
    print(f"  {k}: {v}")
