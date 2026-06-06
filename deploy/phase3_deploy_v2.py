"""
Phase 3: Remote deployment via paramiko SSH.
All operations are fully automated, no user interaction required.
"""
import paramiko
import time
import sys
import os

# === Configuration ===
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server"
GATEWAY_CONTAINER = "gateway-nginx"
NETWORK_NAME = f"{DEPLOY_ID}-network"

ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
ACR_BASE_NS = "noob_doker_base"

GIT_URL = "https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"

DB_PASSWORD = "bini_health_2026"
DB_NAME = "bini_health"

results = {}

def ssh_exec(ssh, cmd, timeout=120, get_pty=False):
    """Execute SSH command and return (stdout, stderr, exit_code)."""
    print(f"  CMD: {cmd[:100]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=get_pty)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(f"  OUT: {out[:500]}")
    if err and exit_code != 0:
        print(f"  ERR: {err[:300]}")
    return out, err, exit_code

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
        print("=== SSH 连接成功 ===\n")
    except Exception as e:
        print(f"SSH 连接失败: {e}")
        sys.exit(1)

    # === Step 1: ACR Login ===
    print("=== Step 1: ACR Login ===")
    out, err, ec = ssh_exec(ssh, f"docker login --username={ACR_USER} --password={ACR_PASS} {ACR_ADDR} 2>&1")
    results['acr_login'] = 'OK' if ec == 0 else f'FAIL: {err}'
    print(f"  Result: {results['acr_login']}")

    # === Step 2: Docker Hub mirror check ===
    print("\n=== Step 2: Docker Hub mirror ===")
    out, err, ec = ssh_exec(ssh, "cat /etc/docker/daemon.json 2>/dev/null | grep -q 'registry-mirrors' && echo '已配置' || echo '未配置'")
    print(f"  Mirror: {out}")

    # === Step 3: Git pull latest code ===
    print("\n=== Step 3: Git pull latest code ===")
    # Check if project directory exists
    out, err, ec = ssh_exec(ssh, f"test -d {PROJECT_DIR} && echo 'EXISTS' || echo 'NOT_EXISTS'")
    if 'EXISTS' in out:
        print("  项目目录已存在，执行 git fetch + reset")
        out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && timeout 30 git fetch --depth 1 codeup master 2>&1 || echo 'FETCH_FAILED'", timeout=45)
        print(f"  Fetch: {out[:200]}")
        if 'FETCH_FAILED' not in out:
            out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && git reset --hard codeup/master 2>&1 && git clean -fd 2>&1")
            print(f"  Reset: {out[:200]}")
        else:
            results['git'] = 'FETCH_FAILED'
    else:
        print("  首次部署，执行 git clone")
        out, err, ec = ssh_exec(ssh, f"timeout 60 git clone --depth 1 --single-branch {GIT_URL} {PROJECT_DIR} 2>&1", timeout=90)
        print(f"  Clone: {out[:500]}")
    
    # Verify git state
    out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --oneline 2>&1")
    results['git_commit'] = out
    print(f"  Latest commit: {out}")

    # === Step 4: Generate BUILD_COMMIT ===
    print("\n=== Step 4: BUILD_COMMIT ===")
    out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'rsync-$(date +%Y%m%d%H%M%S)'")
    build_commit = out.strip().strip("'")
    results['build_commit'] = build_commit
    print(f"  BUILD_COMMIT={build_commit}")

    # === Step 5: Docker compose build & start ===
    print("\n=== Step 5: Docker compose build & start ===")
    
    # Down old containers first
    ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml down 2>&1 || true")
    
    # Build with --pull
    out, err, ec = ssh_exec(ssh, 
        f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml build --pull 2>&1",
        timeout=600)
    print(f"  Build result: ec={ec}")
    if ec != 0:
        # Retry without --pull
        print("  构建失败，尝试不使用 --pull 重试...")
        out, err, ec = ssh_exec(ssh,
            f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml build 2>&1",
            timeout=600)
    
    results['build'] = 'OK' if ec == 0 else f'FAIL: {err[:200]}'
    
    # Start containers
    out, err, ec = ssh_exec(ssh,
        f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml up -d 2>&1",
        timeout=120)
    print(f"  Up result: {out[:300]}")

    # === Step 6: Wait for health checks ===
    print("\n=== Step 6: Wait for health checks ===")
    max_wait = 36  # 3 minutes max
    wait_count = 0
    all_healthy = False
    while wait_count < max_wait:
        time.sleep(10)
        wait_count += 1
        out, err, ec = ssh_exec(ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
            timeout=15)
        if out:
            total = out.count('"Name"')
            healthy = out.count('"Health":"healthy"')
            unhealthy = out.count('"Health":"unhealthy"')
            print(f"  [{wait_count}/{max_wait}] healthy={healthy} unhealthy={unhealthy} total~{total}")
            if total > 0 and healthy >= total - unhealthy:
                all_healthy = True
                break
        else:
            print(f"  [{wait_count}/{max_wait}] waiting for containers...")
    
    results['health'] = 'ALL_HEALTHY' if all_healthy else 'TIMEOUT'
    
    # Show container status
    out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1")
    print(f"  Containers:\n{out}")

    # === Step 7: Connect gateway to project network ===
    print("\n=== Step 7: Gateway network connection ===")
    ssh_exec(ssh, f"docker network connect {NETWORK_NAME} {GATEWAY_CONTAINER} 2>&1 || true")
    out, err, ec = ssh_exec(ssh, f"docker network inspect {NETWORK_NAME} --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}' 2>&1")
    print(f"  Network members: {out}")

    # === Step 8: Deploy gateway server config ===
    print("\n=== Step 8: Gateway config deployment ===")
    
    # Backup old config
    ssh_exec(ssh, f"mkdir -p /home/ubuntu/gateway/conf.d.bak/")
    ssh_exec(ssh, f"cp {GATEWAY_CONF} /home/ubuntu/gateway/conf.d.bak/{DEPLOY_ID}.server.bak.{int(time.time())} 2>&1 || echo 'no_old_config'")
    
    # Deploy gateway config via SFTP
    local_conf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gateway-routes.conf")
    
    sftp = ssh.open_sftp()
    try:
        sftp.put(local_conf_path, "/tmp/gateway_conf_new.conf")
        ssh_exec(ssh, f"cp /tmp/gateway_conf_new.conf {GATEWAY_CONF}")
        ssh_exec(ssh, "rm -f /tmp/gateway_conf_new.conf")
    finally:
        sftp.close()
    
    # Verify config deployed
    out, err, ec = ssh_exec(ssh, f"wc -l {GATEWAY_CONF}")
    print(f"  Config lines: {out}")

    # Test nginx config
    out, err, ec = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
    results['nginx_test'] = 'OK' if ec == 0 else f'FAIL: {err}'
    print(f"  Nginx test: {results['nginx_test']}")
    
    if ec != 0:
        print("  Nginx test failed! Attempting to restore backup...")
        ssh_exec(ssh, f"cp {GATEWAY_CONF}.bak.* {GATEWAY_CONF} 2>&1 || echo 'no_backup'")
        out, err, ec = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
        print(f"  After restore: {out[:200]}")
    
    # Reload nginx
    if ec == 0:
        out, err, ec = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
        print(f"  Reload: {out}")

    # SSL verification
    time.sleep(2)
    out, err, ec = ssh_exec(ssh, f"curl -vI https://{DOMAIN}/ 2>&1 | grep -iE 'SSL|subject|issuer|expire|HTTP/'", timeout=15)
    results['ssl_verify'] = out
    print(f"  SSL verify: {out}")

    # === Step 9: Database migration ===
    print("\n=== Step 9: Database migration ===")
    # Wait for backend to be fully ready
    time.sleep(10)
    
    # Check if database has tables
    check_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
from app.database import engine
from sqlalchemy import inspect
try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(len(tables))
except Exception as e:
    print('0')
    print(f'ERROR:{{e}}')
" 2>&1"""
    out, err, ec = ssh_exec(ssh, check_cmd, timeout=30)
    
    try:
        table_count = int(out.split('\n')[0].strip())
    except:
        table_count = 0
    
    print(f"  Current tables: {table_count}")
    
    if table_count == 0:
        print("  数据库为空，执行 create_all 建表...")
        create_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('所有表已创建')
" 2>&1"""
        out, err, ec = ssh_exec(ssh, create_cmd, timeout=60)
        print(f"  Create result: {out}")
        results['db_migration'] = 'CREATED'
    else:
        print(f"  数据库已有 {table_count} 张表，执行 create_all（已存在的表自动跳过）...")
        create_cmd = f"""docker exec {DEPLOY_ID}-backend python3 -c "
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('增量建表完成')
" 2>&1"""
        out, err, ec = ssh_exec(ssh, create_cmd, timeout=60)
        print(f"  Migration result: {out}")
        results['db_migration'] = 'UPDATED'
    
    # Verify tables
    out, err, ec = ssh_exec(ssh, check_cmd, timeout=30)
    print(f"  Tables after migration: {out.split(chr(10))[0] if out else 'N/A'}")

    # === Step 10: Check default admin account ===
    print("\n=== Step 10: Default admin account ===")
    time.sleep(5)
    
    # Try to login
    login_cmd = f"docker exec {DEPLOY_ID}-backend curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{{\"username\":\"admin\",\"password\":\"admin123\"}}' 2>&1"
    out, err, ec = ssh_exec(ssh, login_cmd, timeout=15)
    
    if 'access_token' in out or '"code":200' in out.lower():
        print("  默认账号 admin/admin123 已存在且可用")
        results['admin_account'] = 'EXISTS'
    else:
        print("  默认账号不存在，尝试创建...")
        # Try register API
        reg_cmd = f"docker exec {DEPLOY_ID}-backend curl -s -X POST http://localhost:8000/api/auth/register -H 'Content-Type: application/json' -d '{{\"username\":\"admin\",\"password\":\"admin123\"}}' 2>&1"
        out, err, ec = ssh_exec(ssh, reg_cmd, timeout=15)
        print(f"  Register: {out[:200]}")
        
        # Verify again
        out, err, ec = ssh_exec(ssh, login_cmd, timeout=15)
        if 'access_token' in out or '"code":200' in out.lower():
            print("  默认账号创建成功")
            results['admin_account'] = 'CREATED'
        else:
            print(f"  账号创建可能失败: {out[:200]}")
            results['admin_account'] = 'FAILED'

    # === Step 11: Final verification ===
    print("\n=== Step 11: Final verification ===")
    
    # Container status
    out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1")
    results['final_containers'] = out
    print(f"  Containers:\n{out}")
    
    # HTTPS check
    out, err, ec = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/ 2>&1", timeout=15)
    results['https_status'] = out
    print(f"  HTTPS status: {out}")
    
    # API check
    out, err, ec = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health 2>&1", timeout=15)
    results['api_status'] = out
    print(f"  API health: {out}")
    
    # Admin check
    out, err, ec = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/admin/ 2>&1", timeout=15)
    results['admin_status'] = out
    print(f"  Admin status: {out}")
    
    ssh.close()
    
    # === Summary ===
    print("\n" + "="*60)
    print("=== 部署完成 ===")
    print("="*60)
    print(f"DEPLOY_ID: {DEPLOY_ID}")
    print(f"项目域名: https://{DOMAIN}")
    print(f"Git commit: {results.get('git_commit', 'N/A')}")
    print(f"ACR Login: {results.get('acr_login', 'N/A')}")
    print(f"Build: {results.get('build', 'N/A')}")
    print(f"Health: {results.get('health', 'N/A')}")
    print(f"Nginx test: {results.get('nginx_test', 'N/A')}")
    print(f"DB migration: {results.get('db_migration', 'N/A')}")
    print(f"Admin account: {results.get('admin_account', 'N/A')}")
    print(f"HTTPS: {results.get('https_status', 'N/A')}")
    print(f"API: {results.get('api_status', 'N/A')}")
    print(f"Admin: {results.get('admin_status', 'N/A')}")
    print(f"SSL: {results.get('ssl_verify', 'N/A')}")
    
    return results

if __name__ == "__main__":
    main()
