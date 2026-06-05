"""Process raw routes and build complete route list."""
import re, json, os

BASE = r"C:\auto_output\bnbbaijkgj"

# ── Backend routes ──
raw = open(os.path.join(BASE, "be_routes.txt"), encoding="utf-8").read()
routes = set()
for line in raw.split("\n"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    m = re.search(r'@(\w+)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', line, re.I)
    if m:
        method = m.group(2).upper()
        path = m.group(3)
        routes.add((method, path))

# Also main.py
main_fp = os.path.join(BASE, "backend", "app", "main.py")
try:
    with open(main_fp, encoding="utf-8", errors="replace") as f:
        content = f.read()
    for m in re.finditer(r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', content, re.I):
        routes.add((m.group(1).upper(), m.group(2)))
except:
    pass

# Add prefixes to routes by reading each file
api_dir = os.path.join(BASE, "backend", "app", "api")
file_prefixes = {}
for fn in os.listdir(api_dir):
    if not fn.endswith(".py") or fn == "__init__.py":
        continue
    fp = os.path.join(api_dir, fn)
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            content = f.read()
        pm = re.search(r'prefix\s*=\s*["\']([^"\']+)', content)
        if pm:
            file_prefixes[fn] = pm.group(1)
        # Also check for routes in this file with prefix
        for m in re.finditer(r'@(\w+)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', content, re.I):
            method = m.group(2).upper()
            path = m.group(3)
            prefix = pm.group(1) if pm else ""
            full = (prefix + path).replace("//", "/")
            if not full.startswith("/"):
                full = "/" + full
            routes.add((method, full))
    except:
        continue

# Also include routes from health endpoint and other main.py routes
routes.add(("GET", "/api/health"))
routes.add(("GET", "/api/docs"))
routes.add(("GET", "/api/redoc"))
routes.add(("GET", "/api/openapi.json"))

backend = sorted([{"method": m, "path": p} for m, p in routes], key=lambda x: (x["path"], x["method"]))

# ── H5 frontend routes (from earlier output) ──
# Use dir /b /s to get page files quickly
import subprocess
def get_next_pages(src_dir, output_var):
    cmd = f'dir /b /s "{src_dir}\\page.tsx" "{src_dir}\\page.ts" 2>nul'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE)
    lines = [l.strip() for l in result.stdout.split("\n") if l.strip() and "page." in l]
    base = src_dir + "\\"
    pages = []
    for l in lines:
        rel = l.replace(base, "").replace("\\", "/")
        # Remove file name, get directory path
        d = os.path.dirname(rel)
        segs = [s for s in d.split("/") if not (s.startswith("(") and s.endswith(")"))]
        path = "/" + "/".join(segs) if segs else "/"
        path = path.replace("//", "/") or "/"
        pages.append(path)
    return sorted(list(set(pages)))

h5_pages = get_next_pages(os.path.join(BASE, "h5-web", "src", "app"), "h5")
admin_pages = get_next_pages(os.path.join(BASE, "admin-web", "src", "app"), "admin")

# ── Output ──
out = {
    "backend": backend,
    "h5_pages": h5_pages,
    "admin_pages": admin_pages,
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
print(f"Output: {out_path}")
