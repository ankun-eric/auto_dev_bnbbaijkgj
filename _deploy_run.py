#!/usr/bin/env python3
"""全自动部署脚本 - 6b099ed3"""
import paramiko
import time
import sys
import re

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
GATEWAY_CONTAINER = "gateway-nginx"
GIT_URL = "https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

def ssh_cmd(client, cmd, timeout=120):
    """执行远程命令并返回 stdout, stderr"""
    print(f"  [CMD] {cmd[:120]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if err and 'warning' not in err.lower():
        print(f"  [STDERR] {err[:200]}")
    return out.strip(), err.strip()

def step(msg):
    print(f"\n{'='*60}")
    print(f">>> {msg}")
    print(f"{'='*60}")

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
        print(f"SSH 连接成功: {USER}@{HOST}")
    except Exception as e:
        print(f"SSH 连接失败: {e}")
        return False
    
    try:
        # ==========================================
        # Step 1: ACR 登录 + Docker 镜像加速器
        # ==========================================
        step("Step 1: ACR 登录")
        out, err = ssh_cmd(client, f"docker login --username {ACR_USER} --password {ACR_PASS} {ACR_REGISTRY} 2>&1")
        print(f"  ACR login: {out[:200]}")
        
        # ==========================================
        # Step 2: 项目代码获取
        # ==========================================
        step("Step 2: 项目代码获取")

        # Check if project directory exists
        out, err = ssh_cmd(client, f"ls {PROJECT_DIR}/docker-compose.prod.yml 2>&1")
        if 'No such file' in out or 'cannot access' in out:
            print("  项目目录不存在，正在 clone...")
            out, err = ssh_cmd(client, f"git clone {GIT_URL} {PROJECT_DIR} 2>&1", timeout=120)
            print(f"  Clone: {out[:200]}")
        else:
            print("  项目目录存在，正在 fetch + reset...")
            out, err = ssh_cmd(client, f"cd {PROJECT_DIR} && git fetch origin master 2>&1 && git reset --hard origin/master 2>&1", timeout=120)
            print(f"  Fetch: {out[:200]}")
        
        # Verify files
        out, err = ssh_cmd(client, f"ls {PROJECT_DIR}/docker-compose.prod.yml && ls {PROJECT_DIR}/h5-web/Dockerfile && ls {PROJECT_DIR}/backend/Dockerfile")
        print(f"  关键文件: {'OK' if 'Dockerfile' in out else 'MISSING!'}")


        # ==========================================
        # Step 3: Docker Compose Build
        # ==========================================
        step("Step 3: Docker Compose Build (h5-web only - frontend change)")
        
        # Build only h5-web since only frontend changed
        out, err = ssh_cmd(client, 
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1",
            timeout=600)
        print(f"  Build result (last 500): ...{out[-500:] if len(out)>500 else out}")
        
        if 'error' in out.lower() and 'ERROR' in out:
            print("  Build 可能有错误，检查输出...")


        # ==========================================
        # Step 4: 重启容器
        # ==========================================
        step("Step 4: 重启 h5-web 容器")
        
        out, err = ssh_cmd(client, 
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1",
            timeout=120)
        print(f"  Up result: {out[:300]}")
        
        # 等待容器启动
        print("  等待 15 秒让容器启动...")
        time.sleep(15)


        # ==========================================
        # Step 5: 容器健康检查
        # ==========================================
        step("Step 5: 容器健康检查")
        
        out, err = ssh_cmd(client, 
            f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}' 2>&1")
        print(f"  容器状态:\n{out}")
        
        # 检查 h5-web 健康
        out, err = ssh_cmd(client,
            f"docker inspect {DEPLOY_ID}-h5 --format '{{{{.State.Health.Status}}}}' 2>&1")
        h5_health = out.strip()
        print(f"  h5-web 健康状态: {h5_health}")


        # ==========================================
        # Step 6: 更新 Gateway 配置
        # ==========================================
        step("Step 6: 更新 Gateway Nginx 配置")
        
        # 生成 gateway 配置
        gateway_conf = f'''# ===== Project: {DEPLOY_ID} =====
server {{
    listen 443 ssl http2;
    server_name {DOMAIN};

    ssl_certificate     /etc/nginx/ssl/wildcard.noob-ai.test.bangbangvip.com.crt;
    ssl_certificate_key /etc/nginx/ssl/wildcard.noob-ai.test.bangbangvip.com.key;

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

    location /uploads/ {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $backend {DEPLOY_ID}-backend;
        proxy_pass http://$backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        expires 30d;
        add_header Cache-Control "public" always;
    }}

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
'''
        # 写入配置文件
        escaped_conf = gateway_conf.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
        out, err = ssh_cmd(client, f"cat > {GATEWAY_CONF} << 'NGXEOF'\n{gateway_conf}\nNGXEOF\n")
        print(f"  配置写入: {'OK' if not err else 'ERR: '+err[:100]}")
        
        # 验证配置
        out, err = ssh_cmd(client, f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
        print(f"  Nginx 配置测试: {out[:300]}")

        
        # 重载 nginx
        if 'successful' in out.lower() or 'ok' in out.lower():
            out, err = ssh_cmd(client, f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
            print(f"  Nginx 重载: {'OK' if not err else err[:100]}")
        else:
            print("  WARNING: nginx -t 失败，跳过重载")
        
        # ==========================================
        # Step 7: 数据库初始化/增量迁移
        # ==========================================
        step("Step 7: 数据库检查")
        
        out, err = ssh_cmd(client,
            f"docker exec {DEPLOY_ID}-backend python3 -c \""
            f"from app.database import engine; "
            f"from app.models.models import Base; "
            f"Base.metadata.create_all(bind=engine); "
            f"print('DB tables ensured')\" 2>&1",
            timeout=30)
        print(f"  DB migration: {out[:200]}")


        # ==========================================
        # Step 8: 验证部署
        # ==========================================
        step("Step 8: 部署验证")
        
        # 测试 H5 首页
        out, err = ssh_cmd(client, f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/ 2>&1")
        h5_status = out.strip()
        print(f"  H5 首页 HTTP 状态: {h5_status}")
        
        # 测试 API 健康检查
        out, err = ssh_cmd(client, f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health 2>&1")
        api_status = out.strip()
        print(f"  API 健康检查 HTTP: {api_status}")
        
        # 测试 Admin
        out, err = ssh_cmd(client, f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/admin/ 2>&1")
        admin_status = out.strip()
        print(f"  Admin HTTP: {admin_status}")
        
        # ==========================================
        # Step 9: 总结
        # ==========================================
        step("Step 9: 部署总结")
        
        # 获取最终容器状态
        out, err = ssh_cmd(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}' 2>&1")
        
        print(f"""
╔══════════════════════════════════════════════════╗
║           部 署 完 成 报 告                       ║
╠══════════════════════════════════════════════════╣
║ 项目 ID:  {DEPLOY_ID}
║ 域  名 :  https://{DOMAIN}
║ H5 首页:  HTTP {h5_status}
║ API 健康:  HTTP {api_status}
║ Admin:    HTTP {admin_status}
╠══════════════════════════════════════════════════╣
║ 容器状态:
{out}
╚══════════════════════════════════════════════════╝
""")
        
        return True
        
    except Exception as e:
        print(f"\n部署异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
