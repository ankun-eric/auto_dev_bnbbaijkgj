"""快速提取所有路由 -- 轻量版"""
import re, json, os

BASE = r"C:\auto_output\bnbbaijkgj"
# Backend
api_dir = os.path.join(BASE, "backend", "app", "api")
routes = set()
prefixes = {}

for fn in os.listdir(api_dir):
    if not fn.endswith(".py") or fn == "__init__.py":
        continue
    fp = os.path.join(api_dir, fn)
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except:
        continue
    # extract prefix
    pm = re.search(r'prefix\s*=\s*["\']([^"\']+)', content)
    prefix = pm.group(1) if pm else ""
    # extract route decorators
    for m in re.finditer(r'@(\w+)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', content, re.I):
        method = m.group(2).upper()
        path = m.group(3)
        fp2 = (prefix + path).replace("//", "/")
        if not fp2.startswith("/"):
            fp2 = "/" + fp2
        routes.add((method, fp2, fn))

# main.py routes
main_fp = os.path.join(BASE, "backend", "app", "main.py")
try:
    with open(main_fp, encoding="utf-8", errors="replace") as f:
        for m in re.finditer(r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', f.read(), re.I):
            routes.add((m.group(1).upper(), m.group(2), "main.py"))
except:
    pass

# H5 routes
h5_src = os.path.join(BASE, "h5-web", "src", "app")
h5_routes = []
for root, dirs, files in os.walk(h5_src):
    for f in files:
        if f.startswith("page.") and (f.endswith(".tsx") or f.endswith(".ts")):
            rel = os.path.relpath(root, h5_src)
            segs = [s for s in rel.replace("\\", "/").split("/") if not (s.startswith("(") and s.endswith(")"))]
            path = "/" + "/".join(segs) if segs else "/"
            path = path.replace("//", "/") or "/"
            h5_routes.append(path)

# Admin routes
admin_src = os.path.join(BASE, "admin-web", "src", "app")
admin_routes = []
for root, dirs, files in os.walk(admin_src):
    for f in files:
        if f.startswith("page.") and (f.endswith(".tsx") or f.endswith(".ts")):
            rel = os.path.relpath(root, admin_src)
            segs = [s for s in rel.replace("\\", "/").split("/") if not (s.startswith("(") and s.endswith(")"))]
            path = "/" + "/".join(segs) if segs else "/"
            path = path.replace("//", "/") or "/"
            admin_routes.append(path)

# Output
out = {
    "backend": sorted([{"method": m, "path": p, "file": f} for m, p, f in routes], key=lambda x: (x["path"], x["method"])),
    "h5": sorted(list(set(h5_routes))),
    "admin": sorted(list(set(admin_routes))),
}

out_path = os.path.join(BASE, "all_routes_extracted.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"Backend: {len(out['backend'])} routes")
print(f"H5: {len(out['h5'])} pages")
print(f"Admin: {len(out['admin'])} pages")
print(f"Output: {out_path}")
