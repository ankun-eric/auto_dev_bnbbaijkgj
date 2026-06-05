#!/usr/bin/env python3
"""通过 SSH 远程扫描 Docker 容器内的路由。"""
import paramiko
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"
H5_CONTAINER = f"{DEPLOY_ID}-h5"
ADMIN_CONTAINER = f"{DEPLOY_ID}-admin"


def ssh_command(ssh_client, cmd, timeout=30):
    """执行远程命令并返回 stdout+stderr。"""
    stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err


def scan_backend_api(ssh_client):
    """扫描后端 API 路由。"""
    print("\n" + "="*60)
    print("扫描后端 API 路由")
    print("="*60)
    
    # Step 1: Find all Python files in /app/backend/app/api/
    cmd = f"docker exec {BACKEND_CONTAINER} find /app/backend/app/api -name '*.py' -type f"
    out, err = ssh_command(ssh_client, cmd)
    files = [f.strip() for f in out.strip().split('\n') if f.strip()]
    print(f"找到 {len(files)} 个 Python 文件")
    
    # Step 2: Collect all APIRouter prefix definitions and route decorators
    all_routes = []
    prefix_map = {}
    
    # First pass: find prefixes
    for fpath in files:
        cmd2 = f"docker exec {BACKEND_CONTAINER} cat {fpath}"
        content, _ = ssh_command(ssh_client, cmd2)
        if not content:
            continue
        
        # Find APIRouter with prefix
        for m in re.finditer(r'(\w+)\s*=\s*APIRouter\s*\(\s*(?:[^)]*?)prefix\s*=\s*["\']([^"\']+)["\']', content):
            var_name = m.group(1)
            prefix = m.group(2)
            key = f"{fpath}::{var_name}"
            prefix_map[key] = prefix
        
        # Find APIRouter without prefix
        for m in re.finditer(r'(\w+)\s*=\s*APIRouter\s*\(', content):
            var_name = m.group(1)
            key = f"{fpath}::{var_name}"
            if key not in prefix_map:
                prefix_map[key] = ''
    
    # Second pass: find route decorators
    for fpath in files:
        cmd2 = f"docker exec {BACKEND_CONTAINER} cat -n {fpath}"
        content, _ = ssh_command(ssh_client, cmd2)
        if not content:
            continue
        
        for line in content.split('\n'):
            # Parse "    linenum\tcode"
            parts = line.split('\t', 1)
            if len(parts) < 2:
                continue
            try:
                lineno = int(parts[0].strip())
            except ValueError:
                continue
            code = parts[1]
            
            m = re.match(r'\s*@(\w+(?:_router)?)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', code)
            if m:
                var_name = m.group(1)
                method = m.group(2).upper()
                path = m.group(3)
                if var_name not in ('app', 'staticmethod', 'classmethod', 'property'):
                    all_routes.append((method, path, fpath, lineno, var_name))
    
    # Also check main.py
    cmd_main = f"docker exec {BACKEND_CONTAINER} cat -n /app/backend/app/main.py"
    content, _ = ssh_command(ssh_client, cmd_main)
    if content:
        for line in content.split('\n'):
            parts = line.split('\t', 1)
            if len(parts) < 2:
                continue
            try:
                lineno = int(parts[0].strip())
            except ValueError:
                continue
            code = parts[1]
            m = re.match(r'\s*@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', code)
            if m:
                method = m.group(1).upper()
                path = m.group(2)
                all_routes.append((method, path, '/app/backend/app/main.py', lineno, 'app'))
    
    # Merge prefixes
    results = []
    for method, path, fpath, lineno, var_name in all_routes:
        key = f"{fpath}::{var_name}"
        prefix = prefix_map.get(key, '')
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
    
    # Dedup
    seen = set()
    unique = []
    for r in results:
        key = (r[0], r[1])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    unique.sort(key=lambda r: ({"GET":0,"POST":1,"PUT":2,"DELETE":3,"PATCH":4}.get(r[0],99), r[1]))
    
    print(f"后端路由总数: {len(unique)}")
    return unique


def scan_frontend_pages(ssh_client, container, app_dir, label):
    """扫描 Next.js App Router 页面路由。"""
    print(f"\n{'='*60}")
    print(f"扫描 {label} 前端页面路由")
    print(f"{'='*60}")
    
    cmd = f"docker exec {container} find {app_dir} -name 'page.tsx' -o -name 'page.ts' -o -name 'page.jsx' -o -name 'page.js' -o -name 'route.ts' -o -name 'route.tsx' | sort"
    out, err = ssh_command(ssh_client, cmd)
    files = [f.strip() for f in out.strip().split('\n') if f.strip()]
    
    print(f"找到 {len(files)} 个路由文件")
    for f in files:
        print(f"  {f}")
    
    routes = []
    for fpath in files:
        # Extract route from path: /app/h5-web/src/app/xxx/page.tsx -> /xxx
        # or /app/h5-web/src/app/page.tsx -> /
        rel = fpath
        if app_dir in rel:
            rel = rel[rel.index(app_dir) + len(app_dir):]
        # Remove /page.tsx or /route.ts etc.
        rel = re.sub(r'/(?:page|route)\.(?:tsx?|jsx?|js)$', '', rel)
        if rel == '':
            rel = '/'
        
        routes.append(rel)
    
    # Dedup and sort
    routes = sorted(set(routes))
    print(f"{label} 页面路由总数: {len(routes)}")
    return routes


def main():
    print("连接 SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
        print("SSH 连接成功！")
    except Exception as e:
        print(f"SSH 连接失败: {e}")
        sys.exit(1)
    
    try:
        # 扫描后端
        backend_routes = scan_backend_api(ssh)
        
        # 扫描 H5 前端
        h5_routes = scan_frontend_pages(ssh, H5_CONTAINER, "/app/h5-web/src/app", "H5")
        
        # 扫描 Admin 前端
        admin_routes = scan_frontend_pages(ssh, ADMIN_CONTAINER, "/app/admin-web/src/app", "Admin")
        
        # 输出结果
        output = {
            "backend_routes": [{"method": r[0], "path": r[1], "file": r[2], "line": r[3]} for r in backend_routes],
            "h5_routes": h5_routes,
            "admin_routes": admin_routes,
            "total_backend": len(backend_routes),
            "total_h5": len(h5_routes),
            "total_admin": len(admin_routes)
        }
        
        # 保存到 JSON 文件
        with open("route_scan_result.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"扫描完成！")
        print(f"  后端路由: {len(backend_routes)}")
        print(f"  H5 页面: {len(h5_routes)}")
        print(f"  Admin 页面: {len(admin_routes)}")
        print(f"结果已保存到 route_scan_result.json")
        
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
