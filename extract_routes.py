"""提取所有前端路由（从 .next 构建文件）。"""
import paramiko
import re
import json

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd, timeout=20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    return out

def extract_routes_from_next(container, label):
    """从 .next/server/app 目录提取路由。"""
    print(f"\n=== {label} ===")
    
    # 获取所有 page.js 文件
    out = run(f'docker exec {container} find /app/.next/server/app -name "page.js" -type f 2>/dev/null')
    routes = []
    
    for fpath in out.strip().split('\n'):
        fpath = fpath.strip()
        if not fpath:
            continue
        # /app/.next/server/app/xxx/page.js -> /xxx
        # /app/.next/server/app/(admin)/xxx/page.js -> /xxx
        # /app/.next/server/app/page.js -> /
        rel = fpath.replace('/app/.next/server/app', '')
        rel = rel.replace('/page.js', '')
        # Remove route group prefixes like (admin)
        rel = re.sub(r'/\([^)]+\)', '', rel)
        if rel == '':
            rel = '/'
        routes.append(rel)
    
    routes = sorted(set(routes))
    print(f"Found {len(routes)} routes:")
    for r in routes:
        print(f"  {r}")
    return routes

def extract_dynamic_routes(container, label):
    """从 routes-manifest.json 提取动态路由。"""
    out = run(f'docker exec {container} cat /app/.next/routes-manifest.json 2>/dev/null')
    try:
        manifest = json.loads(out)
    except:
        print(f"Failed to parse {label} routes-manifest")
        return [], []
    
    redirects = []
    for r in manifest.get('redirects', []):
        redirects.append({
            'source': r.get('source', ''),
            'destination': r.get('destination', ''),
            'statusCode': r.get('statusCode', 0)
        })
    
    dynamic = []
    for d in manifest.get('dynamicRoutes', []):
        dynamic.append(d.get('page', ''))
    
    print(f"\n{label} redirects: {len(redirects)}")
    for r in redirects:
        print(f"  {r['source']} -> {r['destination']} ({r['statusCode']})")
    
    print(f"{label} dynamicRoutes: {len(dynamic)}")
    for d in dynamic:
        print(f"  {d}")
    
    return redirects, dynamic

# Extract
h5_routes = extract_routes_from_next(DEPLOY_ID + '-h5', 'H5')
h5_redirects, h5_dynamic = extract_dynamic_routes(DEPLOY_ID + '-h5', 'H5')

admin_routes = extract_routes_from_next(DEPLOY_ID + '-admin', 'Admin')
admin_redirects, admin_dynamic = extract_dynamic_routes(DEPLOY_ID + '-admin', 'Admin')

# Build full URL list
base_url = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
admin_base = base_url + "/admin"

all_urls = []

# H5 pages
for r in h5_routes:
    all_urls.append({"type": "h5_page", "url": base_url + r, "route": r})

# Admin pages
for r in admin_routes:
    all_urls.append({"type": "admin_page", "url": base_url + "/admin" + r, "route": "/admin" + r})

# Read backend routes from previous scan
with open("route_scan_result.json", "r", encoding="utf-8") as f:
    backend_data = json.load(f)

for r in backend_data.get("backend_routes", []):
    method = r["method"]
    path = r["path"]
    url = base_url + path
    all_urls.append({
        "type": "api",
        "method": method,
        "url": url,
        "route": path,
        "file": r.get("file", ""),
        "line": r.get("line", 0)
    })

# Save full URL list
output = {
    "h5_routes": h5_routes,
    "h5_redirects": h5_redirects,
    "h5_dynamic": h5_dynamic,
    "admin_routes": admin_routes,
    "admin_redirects": admin_redirects,
    "admin_dynamic": admin_dynamic,
    "backend_routes": backend_data.get("backend_routes", []),
    "all_urls": all_urls,
    "summary": {
        "h5_pages": len(h5_routes),
        "admin_pages": len(admin_routes),
        "backend_apis": len(backend_data.get("backend_routes", [])),
        "total": len(all_urls)
    }
}

with open("all_routes.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n=== SUMMARY ===")
print(f"H5 pages: {len(h5_routes)}")
print(f"Admin pages: {len(admin_routes)}")
print(f"Backend APIs: {len(backend_data.get('backend_routes', []))}")
print(f"Total URLs: {len(all_urls)}")
print(f"Saved to all_routes.json")

ssh.close()
