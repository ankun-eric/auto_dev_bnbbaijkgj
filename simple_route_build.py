"""Build route list quickly using pre-existing file lists."""
import re, json, os

BASE = r"C:\auto_output\bnbbaijkgj"
api_dir = os.path.join(BASE, "backend", "app", "api")

# ── Backend: read every API .py file ──
routes = set()
for fn in os.listdir(api_dir):
    if not fn.endswith(".py") or fn == "__init__.py":
        continue
    fp = os.path.join(api_dir, fn)
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except:
        continue
    pm = re.search(r'prefix\s*=\s*["\']([^"\']+)', content)
    prefix = pm.group(1) if pm else ""
    for m in re.finditer(r'@(\w+)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', content, re.I):
        method = m.group(2).upper()
        path = m.group(3)
        full = (prefix + path).replace("//", "/")
        if not full.startswith("/"):
            full = "/" + full
        routes.add((method, full))

# main.py
try:
    with open(os.path.join(BASE, "backend", "app", "main.py"), encoding="utf-8", errors="replace") as f:
        for m in re.finditer(r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', f.read(), re.I):
            routes.add((m.group(1).upper(), m.group(2)))
except:
    pass

routes.add(("GET", "/api/health"))

backend = sorted([{"method": m, "path": p} for m, p in routes], key=lambda x: (x["path"], x["method"]))

# ── H5 / Admin pages: from pre-saved file lists ──
# Use saved file list from earlier dir /b /s commands
# H5 pages
h5_file = os.path.join(BASE, "h5_pages_list.txt")
admin_file = os.path.join(BASE, "admin_pages_list.txt")

# Build from existing data
h5_pages = set()
admin_pages = set()

# Process h5-web pages from the earlier dir output
# Read from saved file or construct
# We'll read the actual file structure using Python's glob which is faster
import glob as gmod
patterns = [
    (os.path.join(BASE, "h5-web", "src", "app", "**", "page.tsx"), "h5"),
    (os.path.join(BASE, "h5-web", "src", "app", "**", "page.ts"), "h5"),
    (os.path.join(BASE, "admin-web", "src", "app", "**", "page.tsx"), "admin"),
    (os.path.join(BASE, "admin-web", "src", "app", "**", "page.ts"), "admin"),
]

for pattern, typ in patterns:
    for fpath in gmod.glob(pattern, recursive=True):
        rel = os.path.relpath(os.path.dirname(fpath), 
              os.path.join(BASE, "h5-web" if typ=="h5" else "admin-web", "src", "app") if typ in ("h5","admin") else "")
        if typ == "h5":
            rel = os.path.relpath(os.path.dirname(fpath), os.path.join(BASE, "h5-web", "src", "app"))
        else:
            rel = os.path.relpath(os.path.dirname(fpath), os.path.join(BASE, "admin-web", "src", "app"))
        segs = [s for s in rel.replace("\\", "/").split("/") if s and not (s.startswith("(") and s.endswith(")"))]
        path = "/" + "/".join(segs) if segs else "/"
        path = path.replace("//", "/") or "/"
        if typ == "h5":
            h5_pages.add(path)
        else:
            admin_pages.add(path)

out = {
    "backend": backend,
    "h5_pages": sorted(h5_pages),
    "admin_pages": sorted(admin_pages),
    "stats": {
        "backend_routes": len(backend),
        "h5_pages": len(h5_pages),
        "admin_pages": len(admin_pages),
    }
}

out_path = os.path.join(BASE, "all_routes_extracted.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out["stats"]))
