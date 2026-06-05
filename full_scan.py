"""全量路由扫描脚本 - 通过 SSH 扫描所有前后端路由。"""
import paramiko
import re
import json
import sys

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
SSH_HOST = "newbb.test.bangbangvip.com"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=22, username='ubuntu', password='Newbang888', timeout=15)
print("SSH Connected", flush=True)

def run(cmd, timeout=20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

# ═══════════════════════════════════════
# 1. 后端 API 路由扫描
# ═══════════════════════════════════════
print("\n=== 扫描后端 API 路由 ===", flush=True)
out, _ = run(f'docker exec {DEPLOY_ID}-backend find /app/app/api -name "*.py" -type f')
api_files = [f.strip() for f in out.strip().split('\n') if f.strip() and f.endswith('.py')]
print(f"API 文件数: {len(api_files)}", flush=True)

# 也检查 main.py 和任何其他路由文件
out, _ = run(f'docker exec {DEPLOY_ID}-backend find /app -name "main.py" -path "*/app/*" -type f')
main_files = [f.strip() for f in out.strip().split('\n') if f.strip()]

# 也搜索 routers 目录
out, _ = run(f'docker exec {DEPLOY_ID}-backend find /app/app -name "*.py" -path "*router*" -type f 2>/dev/null')
router_files = [f.strip() for f in out.strip().split('\n') if f.strip()]

all_py_files = list(set(api_files + main_files + router_files))
print(f"总 Python 文件: {len(all_py_files)}", flush=True)

# 收集 prefix 和 route
prefix_map = {}
routes_raw = []

for fpath in all_py_files:
    out, _ = run(f'docker exec {DEPLOY_ID}-backend cat {fpath}')
    if not out:
        continue
    
    # 找到 APIRouter 定义
    for m in re.finditer(r'(\w+)\s*=\s*APIRouter\s*\(\s*(?:[^)]*?)prefix\s*=\s*["\']([^"\']+)["\']', out):
        var_name = m.group(1)
        prefix = m.group(2)
        prefix_map[(fpath, var_name)] = prefix
    
    for m in re.finditer(r'(\w+)\s*=\s*APIRouter\s*\(', out):
        var_name = m.group(1)
        if (fpath, var_name) not in prefix_map:
            prefix_map[(fpath, var_name)] = ''
    
    # 找到路由装饰器 - 检查每行
    lines = out.split('\n')
    for lineno, line in enumerate(lines, 1):
        # @router.method("path")
        m = re.match(r'\s*@(\w+(?:_router)?)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', line)
        if m:
            var_name = m.group(1)
            method = m.group(2).upper()
            path = m.group(3)
            if var_name not in ('app', 'staticmethod', 'classmethod', 'property'):
                routes_raw.append((method, path, fpath, lineno, var_name))
        
        # @app.method("path")
        m2 = re.match(r'\s*@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', line)
        if m2:
            method = m2.group(1).upper()
            path = m2.group(2)
            routes_raw.append((method, path, fpath, lineno, 'app'))

# 合并 prefix
results = []
for method, path, fpath, lineno, var_name in routes_raw:
    prefix = prefix_map.get((fpath, var_name), '')
    if prefix:
        if prefix.endswith('/') and path.startswith('/'):
            full = prefix + path[1:]
        elif prefix.endswith('/') or path.startswith('/'):
            full = prefix + path
        else:
            full = prefix + '/' + path
    else:
        full = path
    if not full.startswith('/'):
        full = '/' + full
    results.append((method, full, fpath, lineno))

# 去重排序
seen = set()
backend_routes = []
for r in results:
    key = (r[0], r[1])
    if key not in seen:
        seen.add(key)
        backend_routes.append(r)

backend_routes.sort(key=lambda r: ({"GET":0,"POST":1,"PUT":2,"DELETE":3,"PATCH":4}.get(r[0],99), r[1]))

print(f"\n后端路由总数: {len(backend_routes)}", flush=True)
for method, path, fpath, lineno in backend_routes:
    print(f"  {method:6s} {path:50s} <- {fpath}:{lineno}")

# ═══════════════════════════════════════
# 2. H5 前端路由扫描
# ═══════════════════════════════════════
print("\n=== 扫描 H5 前端路由 ===", flush=True)
# 检查是否有 .next 构建清单
out, _ = run(f'docker exec {DEPLOY_ID}-h5 ls /app/')
print(f"H5 /app/ 内容: {out.strip()}")

# 检查 .next 目录
out, _ = run(f'docker exec {DEPLOY_ID}-h5 ls /app/.next 2>/dev/null || echo NO_NEXT_DIR')
h5_routes = []
if 'NO_NEXT_DIR' not in out:
    # 尝试从构建清单获取路由
    out2, _ = run(f'docker exec {DEPLOY_ID}-h5 find /app/.next -name "*pages*" -type f 2>/dev/null | head -20')
    print(f"H5 .next pages: {out2[:500]}")
    
    # 尝试从 server 目录获取路由
    out3, _ = run(f'docker exec {DEPLOY_ID}-h5 ls /app/.next/server/app 2>/dev/null || echo NO_SERVER_APP')
    print(f"H5 .next/server/app: {out3[:1000]}")
    if 'NO_SERVER_APP' not in out3:
        for line in out3.strip().split('\n'):
            line = line.strip()
            if line and not line.endswith('.js') and not line.endswith('.map') and line != 'page':
                h5_routes.append('/' + line)
            elif line == 'page':
                h5_routes.append('/')
else:
    # 没有 .next 目录，尝试其他方式
    out, _ = run(f'docker exec {DEPLOY_ID}-h5 find /app -type d 2>/dev/null | head -50')
    print(f"H5 目录结构: {out[:2000]}")

h5_routes = sorted(set(h5_routes))
print(f"H5 路由: {h5_routes}")

# ═══════════════════════════════════════
# 3. Admin 前端路由扫描
# ═══════════════════════════════════════
print("\n=== 扫描 Admin 前端路由 ===", flush=True)
out, _ = run(f'docker exec {DEPLOY_ID}-admin ls /app/')
print(f"Admin /app/ 内容: {out.strip()}")

out, _ = run(f'docker exec {DEPLOY_ID}-admin ls /app/.next/server/app 2>/dev/null || echo NO_SERVER_APP')
admin_routes = []
if 'NO_SERVER_APP' not in out:
    for line in out.strip().split('\n'):
        line = line.strip()
        if line and not line.endswith('.js') and not line.endswith('.map') and line != 'page':
            admin_routes.append('/' + line)
        elif line == 'page':
            admin_routes.append('/')

admin_routes = sorted(set(admin_routes))
print(f"Admin 路由: {admin_routes}")

# ═══════════════════════════════════════
# 输出结果
# ═══════════════════════════════════════
output = {
    "backend_routes": [{"method": r[0], "path": r[1], "file": r[2], "line": r[3]} for r in backend_routes],
    "h5_routes": h5_routes,
    "admin_routes": admin_routes,
    "total_backend": len(backend_routes),
    "total_h5": len(h5_routes),
    "total_admin": len(admin_routes)
}

with open("route_scan_result.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n=== 汇总 ===")
print(f"后端 API 路由: {len(backend_routes)}")
print(f"H5 页面路由: {len(h5_routes)}")
print(f"Admin 页面路由: {len(admin_routes)}")
print(f"总计: {len(backend_routes) + len(h5_routes) + len(admin_routes)}")
print("结果保存到 route_scan_result.json")

ssh.close()
