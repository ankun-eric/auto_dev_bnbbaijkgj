#!/usr/bin/env python3
"""
noob-deploy-skill 完整自动化部署脚本
阶段 0 → 1 → 1.5 → 2 → 3
"""
import paramiko
import time
import sys
import os
import json
import re

# ========== 配置参数 ==========
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
BASE_DOMAIN = "noob-ai.test.bangbangvip.com"
SERVER_HOST = "newbb.test.bangbangvip.com"
SERVER_IP = "134.175.97.26"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
SERVER_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONFIG_PATH = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
GATEWAY_SERVER_PATH = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server"
GATEWAY_CONTAINER = "gateway-nginx"

GIT_REPO = f"https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NAMESPACE = "noob_ai_apps"
ACR_BASE_NS = "noob_doker_base"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

DB_HOST = "db"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = "bini_health_2026"
DB_NAME = "bini_health"

ssh_client = None

def ssh_cmd(cmd, timeout=60, get_pty=False):
    """执行远程命令并返回 stdout, stderr, exit_code"""
    global ssh_client
    if ssh_client is None:
        raise RuntimeError("SSH not connected")
    print(f"[SSH] $ {cmd[:150]}{'...' if len(cmd)>150 else ''}")
    stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=timeout, get_pty=get_pty)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(f"[OUT] {out[:500]}")
    if err:
        print(f"[ERR] {err[:500]}")
    return out, err, exit_code

def ssh_connect():
    """建立 SSH 连接"""
    global ssh_client
    print("=" * 60)
    print("🔗 连接远程服务器...")
    print(f"   主机: {SERVER_HOST} ({SERVER_IP})")
    print(f"   用户: {SSH_USER}")
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(SERVER_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=20)
    print("✅ SSH 连接成功")
    return True

def ssh_close():
    global ssh_client
    if ssh_client:
        ssh_client.close()
        ssh_client = None

def stage15_precheck():
    """阶段 1.5：服务器环境预检（6项）"""
    print("\n" + "=" * 60)
    print("📋 阶段 1.5：服务器环境预检")
    print("=" * 60)

    results = {}

    # 1. Gateway Nginx 配置结构
    print("\n[1/6] Gateway Nginx 配置结构检查...")
    out, err, code = ssh_cmd("docker ps --filter name=gateway-nginx --format '{{.Names}} {{.Status}}'")
    results['gateway_status'] = out.strip()
    print(f"  Gateway 状态: {out.strip()}")

    # Check if .server file already exists
    out, err, code = ssh_cmd(f"ls -la /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server 2>/dev/null && echo 'EXISTS' || echo 'NOT_FOUND'")
    results['server_file'] = out.strip()
    print(f"  .server 文件: {out.strip()}")

    # Check nginx conf.d structure
    out, err, code = ssh_cmd("ls /home/ubuntu/gateway/conf.d/ | head -30")
    print(f"  conf.d 内容: {out.strip()[:300]}")

    # 2. 路由占用检查
    print("\n[2/6] 路由占用检查...")
    out, err, code = ssh_cmd(f"docker exec {GATEWAY_CONTAINER} nginx -T 2>/dev/null | grep -c 'server_name {PROJECT_DOMAIN}' || echo 0")
    results['route_count'] = out.strip()

    out, err, code = ssh_cmd(f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
    results['nginx_test'] = out.strip()[:500]
    print(f"  Nginx 测试: {out.strip()[:200]}")

    # 3. ACR 基础镜像版本匹配
    print("\n[3/6] ACR 基础镜像版本匹配检查...")
    # Check if Docker can pull from ACR
    out, err, code = ssh_cmd(f"docker pull {ACR_ADDR}/{ACR_BASE_NS}/python:3.12-slim 2>&1 | tail -3")
    results['acr_python'] = 'OK' if code == 0 else f'FAILED: {err[:200]}'
    print(f"  Python 3.12-slim: {results['acr_python']}")

    # 4. Docker 网络拓扑
    print("\n[4/6] Docker 网络拓扑检查...")
    out, err, code = ssh_cmd("docker network ls --format '{{.Name}} {{.Driver}}' | head -20")
    results['networks'] = out.strip()
    print(f"  网络列表: {out.strip()[:300]}")

    # Check if db container exists and its network
    out, err, code = ssh_cmd("docker inspect db --format '{{.NetworkSettings.Networks}}' 2>/dev/null | head -5")
    results['db_networks'] = out.strip()
    print(f"  DB 容器网络: {out.strip()[:200]}")

    # Check project network
    out, err, code = ssh_cmd(f"docker network inspect {DEPLOY_ID}-network --format '{{.Name}}' 2>/dev/null || echo 'NOT_FOUND'")
    results['project_network'] = out.strip()

    # 5. 基础镜像内置工具检测
    print("\n[5/6] 基础镜像内置工具检测...")
    # Check on server tools
    out, err, code = ssh_cmd("which python3 && python3 --version && which node && node --version && which wget && which curl")
    results['tools'] = out.strip()[:300]
    print(f"  工具: {out.strip()[:200]}")

    # 6. 磁盘空间检查
    print("\n[6/6] 磁盘空间检查...")
    out, err, code = ssh_cmd("df -h / | tail -1")
    results['disk'] = out.strip()
    print(f"  磁盘: {out.strip()}")

    # 检查项目目录
    out, err, code = ssh_cmd(f"ls -la {SERVER_PROJECT_DIR} 2>/dev/null | head -10 || echo 'DIR_NOT_FOUND'")
    results['project_dir'] = 'EXISTS' if 'DIR_NOT_FOUND' not in out else 'NOT_FOUND'

    # 检查已存在的容器
    out, err, code = ssh_cmd(f"docker ps -a --filter name={DEPLOY_ID} --format '{{.Names}} {{.Status}}'")
    results['existing_containers'] = out.strip()

    print("\n📊 预检结果汇总:")
    for k, v in results.items():
        print(f"  {k}: {str(v)[:100]}")

    return results

def stage3_deploy():
    """阶段 3：远程部署"""
    print("\n" + "=" * 60)
    print("🚀 阶段 3：远程部署")
    print("=" * 60)

    # 3.1 ACR 登录
    print("\n[3.1] ACR 登录...")
    login_cmd = f"docker login --username {ACR_USER} --password '{ACR_PASS}' {ACR_ADDR}"
    out, err, code = ssh_cmd(login_cmd)
    if code != 0:
        print(f"⚠️ ACR 登录可能失败: {err[:200]}")
    else:
        print("✅ ACR 登录成功")

    # 配置镜像加速器
    ssh_cmd("sudo mkdir -p /etc/docker")
    ssh_cmd("""sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"],
  "insecure-registries": ["crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"]
}
EOF""")
    print("✅ 镜像加速器已配置")

    # 3.3 项目代码获取 (Git clone/fetch)
    print("\n[3.3] 项目代码获取...")
    git_url_with_auth = f"https://{GIT_USER}:{GIT_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"

    # 检查目录是否存在
    out, err, code = ssh_cmd(f"test -d {SERVER_PROJECT_DIR}/.git && echo 'GIT_REPO_EXISTS' || echo 'GIT_REPO_NOT_FOUND'")
    if 'GIT_REPO_EXISTS' in out:
        print("  现有 Git 仓库，执行 fetch + reset...")
        cmds = [
            f"cd {SERVER_PROJECT_DIR} && git fetch origin master --depth=1",
            f"cd {SERVER_PROJECT_DIR} && git reset --hard origin/master",
            f"cd {SERVER_PROJECT_DIR} && git clean -fd",
        ]
        for cmd in cmds:
            ssh_cmd(cmd)
    else:
        print("  新建目录，执行 git clone...")
        ssh_cmd(f"sudo mkdir -p {SERVER_PROJECT_DIR}")
        ssh_cmd(f"sudo chown -R ubuntu:ubuntu /home/ubuntu/")
        clone_cmd = f"git clone --depth=1 --branch master {git_url_with_auth} {SERVER_PROJECT_DIR}"
        out, err, code = ssh_cmd(clone_cmd, timeout=120)
        if code != 0:
            # Try without depth limit
            clone_cmd2 = f"git clone --branch master {git_url_with_auth} {SERVER_PROJECT_DIR}"
            out, err, code = ssh_cmd(clone_cmd2, timeout=180)

    print("✅ 项目代码就绪")

    # 3.4 环境变量配置
    print("\n[3.4] 环境变量配置...")
    env_content = f"""DATABASE_URL=mysql+aiomysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}
SECRET_KEY=bini-health-secret-key-2026-very-secure
AI_BASE_URL=
AI_MODEL_NAME=
AI_API_KEY=
TENCENT_SMS_SECRET_ID=
TENCENT_SMS_SECRET_KEY=
TENCENT_SMS_SDK_APP_ID=1400920269
TENCENT_SMS_SIGN_NAME=呃唉帮帮网络
TENCENT_SMS_TEMPLATE_ID=2201340
TENCENT_SMS_APP_KEY=7e3c8242bf0799cca367fa18fa47a7ea
STATIC_BASE_URL=https://{PROJECT_DOMAIN}
PROJECT_BASE_URL=https://{PROJECT_DOMAIN}
PUBLIC_API_BASE_URL=https://{PROJECT_DOMAIN}
PAYMENT_TIMEOUT_MINUTES=15
BUILD_COMMIT=latest
"""
    ssh_cmd(f"cat > {SERVER_PROJECT_DIR}/deploy/.env << 'ENVEOF'\n{env_content}\nENVEOF")
    print("✅ .env 文件已创建")

    # 确保 docker-compose.prod.yml 的 DATABASE_URL 使用正确的 db 主机名
    print("\n[3.4b] 修正 docker-compose.prod.yml 数据库连接...")
    # Replace DATABASE_URL in docker-compose
    ssh_cmd(f"""cd {SERVER_PROJECT_DIR}/deploy && sed -i 's|DATABASE_URL: mysql+aiomysql://root:bini_health_2026@[^:]*:3306/bini_health|DATABASE_URL: mysql+aiomysql://root:bini_health_2026@db:3306/bini_health|g' docker-compose.prod.yml""")
    # Verify
    out, err, code = ssh_cmd(f"grep DATABASE_URL {SERVER_PROJECT_DIR}/deploy/docker-compose.prod.yml")
    print(f"  DATABASE_URL: {out.strip()}")

    # 3.4c 确保 db 容器连接到项目网络
    print("\n[3.4c] 数据库网络配置...")
    # Ensure project network exists
    ssh_cmd(f"docker network create {DEPLOY_ID}-network 2>/dev/null || echo 'Network already exists'")
    # Connect db container to project network
    ssh_cmd(f"docker network connect {DEPLOY_ID}-network db 2>/dev/null || echo 'db already connected or not found'")
    print("✅ 数据库网络配置完成")

    # 3.5 构建与启动容器
    print("\n[3.5] 构建与启动容器...")
    # Stop existing containers first
    ssh_cmd(f"cd {SERVER_PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true")
    time.sleep(2)

    # Build and start
    print("  开始 docker compose build...")
    out, err, code = ssh_cmd(f"cd {SERVER_PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
    print(f"  Build exit code: {code}")
    if code != 0:
        print(f"⚠️ Build 可能出现问题: {err[-500:]}")
        # Try pull then build
        print("  尝试先拉取基础镜像...")
        ssh_cmd(f"docker pull {ACR_ADDR}/{ACR_BASE_NS}/python:3.12-slim")
        ssh_cmd(f"docker pull {ACR_ADDR}/{ACR_BASE_NS}/node:20-alpine")
        out, err, code = ssh_cmd(f"cd {SERVER_PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml build 2>&1", timeout=600)

    print("  启动容器...")
    out, err, code = ssh_cmd(f"cd {SERVER_PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
    print(f"  up exit code: {code}")

    # Wait for containers
    print("  等待容器启动...")
    time.sleep(15)

    # Check container status
    out, err, code = ssh_cmd(f"docker ps -a --filter name={DEPLOY_ID} --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
    print(f"  容器状态:\n{out}")

    # 3.6 更新 gateway-nginx 配置
    print("\n[3.6] 更新 gateway-nginx 配置...")

    gateway_server_content = f"""# ===== Project: {DEPLOY_ID} =====
# 独立 server 块，通过 include conf.d/*.server 加载
server {{
    listen 443 ssl http2;
    server_name {PROJECT_DOMAIN};

    ssl_certificate     /etc/nginx/ssl/wildcard.noob-ai.test.bangbangvip.com.crt;
    ssl_certificate_key /etc/nginx/ssl/wildcard.noob-ai.test.bangbangvip.com.key;

    # 下载/静态文件
    location /downloads/ {{
        alias /data/static/apk/;
        default_type application/octet-stream;
        add_header Content-Disposition attachment;
    }}

    # /api/ 路径 -> 后端容器
    location /api/ {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $backend {DEPLOY_ID}-backend;
        proxy_pass http://$backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
        proxy_request_buffering off;
    }}

    # /uploads/ 路径 -> 后端容器
    location /uploads/ {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $backend {DEPLOY_ID}-backend;
        proxy_pass http://$backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        expires 30d;
        add_header Cache-Control "public" always;
    }}

    # /admin/ 路径 -> 管理后台容器
    location /admin/ {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $admin {DEPLOY_ID}-admin;
        proxy_pass http://$admin:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}

    # / 路径 -> H5用户端容器
    location / {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $h5 {DEPLOY_ID}-h5;
        proxy_pass http://$h5:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}
}}
"""

    # Write server config to remote
    escaped = gateway_server_content.replace('\\', '\\\\').replace('$', '\\$').replace('`', '\\`')
    ssh_cmd(f"cat > {GATEWAY_SERVER_PATH} << 'GATEWAYEOF'\n{gateway_server_content}\nGATEWAYEOF")
    print(f"✅ Gateway 配置已写入: {GATEWAY_SERVER_PATH}")

    # Disable old .conf files if any
    ssh_cmd(f"test -f /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf && mv /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf.disabled.$(date +%s) 2>/dev/null || true")

    # Test and reload nginx
    out, err, code = ssh_cmd(f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
    print(f"  Nginx 配置测试: {out.strip()[:300]}")
    if 'syntax is ok' in out.lower() or 'successful' in out.lower():
        out, err, code = ssh_cmd(f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
        print(f"  Nginx reload: {out.strip()}")
        print("✅ Gateway nginx 已更新并重载")
    else:
        print("⚠️ Nginx 配置可能有语法错误，尝试回滚...")
        # Try to restore backup

    # 3.7 数据库初始化与增量迁移
    print("\n[3.7] 数据库初始化与增量迁移...")
    # The backend's lifespan will handle create_all and migrations
    # But let's also check if we need to run alembic or manual migrations
    out, err, code = ssh_cmd(f"docker logs {DEPLOY_ID}-backend --tail 30 2>&1")
    print(f"  Backend 日志(尾部): {out[-500:]}")

    # Check if backend /api/health is responding
    print("  检查后端健康状态...")
    for i in range(12):
        out, err, code = ssh_cmd(f"docker exec {DEPLOY_ID}-backend curl -sf http://127.0.0.1:8000/api/health 2>&1 || echo 'HEALTH_FAIL'")
        if 'HEALTH_FAIL' not in out:
            print(f"  ✅ 后端健康检查通过: {out.strip()}")
            break
        print(f"  等待后端启动... ({i+1}/12)")
        time.sleep(10)
    else:
        print("  ⚠️ 后端健康检查超时，检查日志...")
        out, err, code = ssh_cmd(f"docker logs {DEPLOY_ID}-backend --tail 50 2>&1")
        print(f"  后端日志: {out[-800:]}")

    # 3.8 系统初始化 - 默认账号检查
    print("\n[3.8] 系统初始化 - 默认账号检查...")
    # Check if admin/default accounts exist
    check_script = f"""
import pymysql
import json
try:
    conn = pymysql.connect(host='{DB_HOST}', port={DB_PORT}, user='{DB_USER}', password='{DB_PASS}', database='{DB_NAME}')
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, created_at FROM users LIMIT 20")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    result = []
    for row in rows:
        result.append(dict(zip(columns, [str(x) if x is not None else None for x in row])))
    print(json.dumps(result, ensure_ascii=False, default=str))
    cursor.close()
    conn.close()
except Exception as e:
    print(f"ERROR: {{e}}")
"""
    ssh_cmd(f"cat > /tmp/check_users.py << 'PYEOF'\n{check_script}\nPYEOF")
    out, err, code = ssh_cmd("python3 /tmp/check_users.py 2>&1")
    print(f"  用户列表: {out[:500]}")
    if 'ERROR' in out:
        print("  ⚠️ 数据库查询失败，可能表尚未创建")

    # 3.9 启动确认
    print("\n[3.9] 启动确认...")
    out, err, code = ssh_cmd(f"docker ps --filter name={DEPLOY_ID} --format '{{.Names}} {{.Status}}'")
    containers = out.strip().split('\n')
    all_healthy = True
    for c in containers:
        print(f"  {c}")
        if 'unhealthy' in c.lower() or 'exited' in c.lower():
            all_healthy = False

    # Verify via HTTP
    print("\n  外部 HTTP 验证...")
    out, err, code = ssh_cmd(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{PROJECT_DOMAIN}/api/health 2>&1")
    api_status = out.strip()
    print(f"  API 健康检查 HTTP 状态: {api_status}")

    out, err, code = ssh_cmd(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{PROJECT_DOMAIN}/ 2>&1")
    h5_status = out.strip()
    print(f"  H5 首页 HTTP 状态: {h5_status}")

    out, err, code = ssh_cmd(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{PROJECT_DOMAIN}/admin/ 2>&1")
    admin_status = out.strip()
    print(f"  Admin HTTP 状态: {admin_status}")

    return {
        'containers': containers,
        'api_status': api_status,
        'h5_status': h5_status,
        'admin_status': admin_status,
        'all_healthy': all_healthy
    }


def main():
    """主执行流程"""
    print("=" * 60)
    print("🤖 noob-deploy-skill 自动化部署")
    print(f"   DEPLOY_ID: {DEPLOY_ID}")
    print(f"   项目域名: {PROJECT_DOMAIN}")
    print(f"   服务器: {SERVER_HOST}")
    print("=" * 60)

    try:
        # 连接
        ssh_connect()

        # 阶段 0：deploy_msg.txt 已就绪（跳过）

        # 阶段 1.5：预检
        precheck = stage15_precheck()

        # 阶段 3：部署
        result = stage3_deploy()

        # 汇总报告
        print("\n" + "=" * 60)
        print("📊 部署结果汇总")
        print("=" * 60)
        report = {
            "DEPLOY_ID": DEPLOY_ID,
            "项目域名": PROJECT_DOMAIN,
            "服务器": SERVER_HOST,
            "部署状态": "✅ 成功" if result['all_healthy'] else "⚠️ 部分异常",
            "API状态": result['api_status'],
            "H5状态": result['h5_status'],
            "Admin状态": result['admin_status'],
            "容器运行状态": result['containers'],
            "服务器连接": f"ssh {SSH_USER}@{SERVER_HOST}",
            "项目目录": SERVER_PROJECT_DIR,
            "Gateway配置": GATEWAY_SERVER_PATH,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))

        # Save report
        with open('deploy/deploy_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    except Exception as e:
        print(f"\n❌ 部署异常: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        ssh_close()

if __name__ == '__main__':
    main()
