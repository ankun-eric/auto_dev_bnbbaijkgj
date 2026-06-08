"""
Stage 3: Full remote deployment using SFTP for file transfers.
"""
import paramiko
import time
import sys
import os

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = "noob-ai.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
NGINX_CONF = "/home/ubuntu/gateway/nginx.conf"
ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

def ssh_exec(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print("[1/10] Connecting...")
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
    sftp = client.open_sftp()
    print("Connected!\n")
    
    # ===== Git pull =====
    print("[2/10] Git pull...")
    git_auth = f"https://{GIT_USER}:{GIT_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
    out, _, ec = ssh_exec(client, f"test -d {PROJECT_DIR} && echo 'EXISTS' || echo 'NOT_EXISTS'")
    if 'EXISTS' in out:
        cmds = f"cd {PROJECT_DIR} && git remote set-url codeup '{git_auth}' 2>/dev/null; git fetch codeup master 2>&1; git reset --hard codeup/master 2>&1; git clean -fd 2>&1; git log -1 --oneline"
        out, err, ec = ssh_exec(client, cmds, timeout=60)
        print(f"Pull: {out[:500]}")
    else:
        cmd = f"git clone --depth 1 --single-branch '{git_auth}' {PROJECT_DIR} 2>&1"
        out, err, ec = ssh_exec(client, cmd, timeout=120)
        print(f"Clone: {out[:300]}")
    
    # ===== ACR login =====
    print("\n[3/10] ACR login...")
    out, _, _ = ssh_exec(client, f"docker login --username={ACR_USER} --password='{ACR_PASS}' {ACR_ADDR} 2>&1")
    print(f"ACR: {out.strip()[:200]}")
    
    # ===== BUILD_COMMIT =====
    print("\n[4/10] BUILD_COMMIT...")
    out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown'")
    build_commit = out.strip().replace("'", "")
    print(f"BUILD_COMMIT={build_commit}")
    
    # ===== Docker compose down old =====
    print("\n[5/10] Stop old containers...")
    out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml down 2>&1 || true")
    print(f"Down: {out.strip()[:200]}")
    
    # ===== Docker compose build =====
    print("\n[6/10] Build containers (this takes a while)...")
    cmd = f"cd {PROJECT_DIR}/deploy && BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml build --pull 2>&1"
    out, err, ec = ssh_exec(client, cmd, timeout=600)
    if ec != 0:
        print(f"Build had issues, retrying without --pull...")
        print(f"Error tail: {err[-500:]}")
        cmd2 = f"cd {PROJECT_DIR}/deploy && BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml build 2>&1"
        out, err, ec = ssh_exec(client, cmd2, timeout=600)
    print(f"Build done. Last output: {out[-300:]}")
    
    # ===== Docker compose up =====
    print("\n[7/10] Start containers...")
    out, err, ec = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=60)
    print(f"Up: {out.strip()[:300]}")
    if err.strip():
        print(f"Errors: {err.strip()[:300]}")

    # ===== Wait for health =====
    print("\n[8/10] Wait for health checks...")
    all_healthy = False
    for i in range(36):
        time.sleep(5)
        out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null")
        healthy = out.count('"Health":"healthy"')
        total = max(len([l for l in out.split('\n') if l.strip()]), 1)
        print(f"  [{i+1}/36] {healthy}/{total} healthy")
        if healthy >= total and healthy >= 3:
            all_healthy = True
            print("All healthy!")
            break
    
    if not all_healthy:
        print("Warning: not all containers healthy")
        out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps 2>&1")
        print(out)
    
    # ===== Gateway network =====
    print("\n[9/10] Connect gateway to network...")
    out, _, _ = ssh_exec(client, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || echo 'ALREADY'")
    print(out.strip()[:200])
    
    # ===== Upload config files via SFTP =====
    print("\n[10/10] Update gateway nginx config...")
    
    # Upload insert script
    local_insert = os.path.join(LOCAL_DIR, "deploy", "insert_nginx_server.py")
    sftp.put(local_insert, "/tmp/insert_nginx_server.py")
    
    # Upload gateway-routes.conf
    local_routes = os.path.join(LOCAL_DIR, "deploy", "gateway-routes.conf")
    sftp.put(local_routes, "/tmp/gateway-routes.conf")
    
    # Backup old conf
    ssh_exec(client, f"mkdir -p /home/ubuntu/gateway/conf.d.bak && cp {GATEWAY_CONF} /home/ubuntu/gateway/conf.d.bak/{DEPLOY_ID}.conf.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null; echo OK")
    
    # Run insert script
    out, err, ec = ssh_exec(client, f"python3 /tmp/insert_nginx_server.py '{DEPLOY_ID}' '{WILDCARD_BASE}' 2>&1")
    print(f"Insert result: {out.strip()[:300]}")
    if err.strip():
        print(f"Insert err: {err.strip()[:200]}")
    
    # Copy conf file
    out, err, ec = ssh_exec(client, f"cp /tmp/gateway-routes.conf {GATEWAY_CONF} && echo 'CONF_OK'")
    print(f"Copy conf: {out.strip()}")
    
    # Test nginx
    out, err, ec = ssh_exec(client, "docker exec gateway-nginx nginx -t 2>&1")
    print(f"Nginx test: {out.strip()} {err.strip()}")
    
    if ec == 0:
        out, err, ec = ssh_exec(client, "docker exec gateway-nginx nginx -s reload 2>&1")
        print(f"Reload: {out.strip()} {err.strip()}")
        time.sleep(2)
    
    # ===== DB init =====
    print("\n[11/11] Database init...")
    out, _, _ = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"from app.database import engine, Base; from sqlalchemy import inspect; inspector = inspect(engine); tables = inspector.get_table_names(); print(f'TABLES: {len(tables)}'); [print(t) for t in sorted(tables)]\" 2>&1", timeout=30)
    print(f"DB: {out[:500]}")
    
    if 'TABLES: 0' in out or 'Error' in out:
        out2, _, _ = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"from app.database import Base, engine; Base.metadata.create_all(bind=engine); print('CREATED')\" 2>&1", timeout=30)
        print(f"Create: {out2[:300]}")
    else:
        out2, _, _ = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"from app.database import Base, engine; Base.metadata.create_all(bind=engine); print('UPDATED')\" 2>&1", timeout=30)
        print(f"Update: {out2[:300]}")
    
    # ===== Admin account =====
    print("\n[12/12] Admin account check...")
    out, _, _ = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"" + 
        "import urllib.request, json; " +
        "req = urllib.request.Request('http://localhost:8000/api/auth/login', " +
        "data=json.dumps({'username':'admin','password':'admin123'}).encode(), " +
        "headers={'Content-Type':'application/json'}, method='POST'); " +
        "try: resp = urllib.request.urlopen(req, timeout=10); print(f'LOGIN_STATUS: {resp.status}') " +
        "except Exception as e: print(f'LOGIN_FAIL: {e}')\" 2>&1", timeout=20)
    print(f"Admin: {out.strip()[:200]}")
    
    if 'LOGIN_OK' not in out and '200' not in out:
        print("Creating admin account via DB...")
        out2, _, _ = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"" + 
            "from app.database import SessionLocal; " +
            "from app.models.models import User; " +
            "from app.core.security import get_password_hash; " +
            "db = SessionLocal(); " +
            "u = db.query(User).filter(User.username == 'admin').first(); " +
            "if not u: " +
            "  user = User(username='admin', hashed_password=get_password_hash('admin123'), is_admin=True); " +
            "  db.add(user); db.commit(); print('ADMIN_CREATED') " +
            "else: print('ADMIN_EXISTS') " +
            "db.close()\" 2>&1", timeout=20)
        print(f"Admin create: {out2[:300]}")
    
    # ===== Final =====
    print("\n" + "="*60)
    print("DEPLOYMENT FINISHED")
    print(f"DEPLOY_ID: {DEPLOY_ID}")
    print(f"URL: https://{DEPLOY_ID}.{WILDCARD_BASE}")
    print(f"Admin: https://{DEPLOY_ID}.{WILDCARD_BASE}/admin/")
    print(f"Server: ssh {USER}@{HOST}")
    
    out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps 2>&1")
    print(f"\nContainers:\n{out}")
    
    sftp.close()
    client.close()

if __name__ == '__main__':
    main()
