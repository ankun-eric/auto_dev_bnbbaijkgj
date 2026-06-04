"""
阶段 1.5：服务器环境预检（6项）
通过 SSH 执行：
1. Gateway nginx 配置结构探测
2. 路由占用检查
3. ACR 基础镜像版本匹配
4. Docker 网络拓扑
5. 基础镜像内置工具检测
6. 磁盘空间检查
"""
import paramiko
import json
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_BASE_NS = "noob_doker_base"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

def ssh_exec(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out.strip(), err.strip()

results = {}

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
    print("[OK] SSH connected to", HOST)


    # ===== 1. Gateway nginx 配置结构探测 =====
    print("\n===== [1/6] Gateway nginx 配置结构 =====")
    out, err = ssh_exec(ssh, "docker ps --filter name=gateway-nginx --format '{{.Names}} {{.Status}}'")
    print("gateway-nginx container:", out)
    
    out, err = ssh_exec(ssh, "docker exec gateway-nginx cat /etc/nginx/nginx.conf 2>/dev/null | grep -n 'include conf.d' || echo 'NOT_FOUND'")
    print("include conf.d line:", out)
    
    out, err = ssh_exec(ssh, "docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null | head -20")
    print("conf.d files:", out)
    
    # Check existing config for this project
    out, err = ssh_exec(ssh, f"docker exec gateway-nginx cat /etc/nginx/conf.d/{DEPLOY_ID}.conf 2>/dev/null | head -5 || echo 'FILE_NOT_FOUND'")
    print(f"Existing {DEPLOY_ID}.conf:", out[:200])
    results['gateway_config'] = out[:300]

    # ===== 2. 路由占用检查 =====
    print("\n===== [2/6] 路由占用检查 =====")
    out, err = ssh_exec(ssh, f"docker exec gateway-nginx grep -l 'location /' /etc/nginx/conf.d/*.conf 2>/dev/null || echo 'NONE'")
    print("conf files with 'location /':", out)
    
    out, err = ssh_exec(ssh, f"docker exec gateway-nginx grep -l 'location /api/' /etc/nginx/conf.d/*.conf 2>/dev/null || echo 'NONE'")
    print("conf files with 'location /api/':", out)
    results['route_usage'] = {'location_root': out, 'location_api': out}

    # ===== 3. ACR 基础镜像版本匹配 =====
    print("\n===== [3/6] ACR 基础镜像版本检查 =====")
    out, err = ssh_exec(ssh, "docker login --username ankun888 --password xiaobai888 crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com 2>&1")
    print("ACR login:", "OK" if "Login Succeeded" in out else "FAILED")
    
    # Check if Python 3.12-slim base exists
    out, err = ssh_exec(ssh, "docker pull crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim 2>&1 | tail -3")
    print("python:3.12-slim pull:", out)
    
    out, err = ssh_exec(ssh, "docker pull crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/node:20-alpine 2>&1 | tail -3")
    print("node:20-alpine pull:", out)
    results['acr_base_images'] = "pulled"



    # ===== 4. Docker 网络拓扑 =====
    print("\n===== [4/6] Docker 网络拓扑 =====")
    out, err = ssh_exec(ssh, "docker network ls | grep gateway || echo 'NO_GATEWAY_NETWORK'")
    print("gateway networks:", out)
    
    network_cmd = "docker network inspect " + DEPLOY_ID + "-network 2>&1 | head -20"
    out, err = ssh_exec(ssh, network_cmd)
    print("project network:", out[:500])
    
    out, err = ssh_exec(ssh, "docker inspect gateway-nginx --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null")
    print("gateway-nginx networks:", out)
    results['network_topo'] = out

    # ===== 5. 基础镜像内置工具检测 =====
    print("\n===== [5/6] 基础镜像内置工具检测 =====")
    # Test in a temporary container
    out, err = ssh_exec(ssh, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim which python3 wget curl 2>/dev/null || echo 'TOOLS_CHECK'")
    print("python image tools:", out)
    
    out, err = ssh_exec(ssh, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/node:20-alpine which node wget curl 2>/dev/null || echo 'TOOLS_CHECK'")
    print("node image tools:", out)
    
    # Alternative: check with sh -c
    out, err = ssh_exec(ssh, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim sh -c 'which python3 && which wget || which curl || echo NO_TOOL' 2>/dev/null")
    print("python tools detailed:", out)
    
    out, err = ssh_exec(ssh, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/node:20-alpine sh -c 'which node && which wget || which curl || echo NO_TOOL' 2>/dev/null")
    print("node tools detailed:", out)
    results['tool_check'] = {'python': out, 'node': None}

    # ===== 6. 磁盘空间检查 =====
    print("\n===== [6/6] 磁盘空间检查 =====")
    out, err = ssh_exec(ssh, "df -h / | tail -1")
    print("disk usage:", out)
    
    out, err = ssh_exec(ssh, "docker system df 2>/dev/null || echo 'NO_DOCKER_DF'")
    print("docker disk usage:", out)
    results['disk_space'] = out

    ssh.close()
    print("\n===== ALL PRECHECKS COMPLETED =====")
    
except Exception as e:
    print(f"[FATAL] SSH precheck failed: {e}")
    sys.exit(1)
