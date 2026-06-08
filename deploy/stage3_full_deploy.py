"""
Stage 3: Full remote deployment script.
- Git pull on server
- ACR login
- Docker compose build & up
- Gateway nginx config update (nested mode)
- Database init / migration
- Default admin account creation
"""
import paramiko
import time
import json
import sys

# === Config ===
HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = "noob-ai.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF_DIR = "/home/ubuntu/gateway/conf.d"
GATEWAY_CONF = f"{GATEWAY_CONF_DIR}/{DEPLOY_ID}.conf"
NGINX_CONF = "/home/ubuntu/gateway/nginx.conf"
ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS_APPS = "noob_ai_apps"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
GIT_REPO = "https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

def ssh_exec(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def run():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print("[1/10] Connecting to server...")
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
    print("Connected!\n")
    
    # ===== Step 1: Git pull / clone =====
    print("[2/10] Git pull latest code...")
    check_dir, _, ec = ssh_exec(client, f"test -d {PROJECT_DIR} && echo 'EXISTS' || echo 'NOT_EXISTS'")
    if 'EXISTS' in check_dir:
        git_auth_url = f"https://{GIT_USER}:{GIT_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
        cmds = [
            f"cd {PROJECT_DIR}",
            f"git remote set-url codeup '{git_auth_url}' 2>/dev/null || git remote add codeup '{git_auth_url}'",
            "git fetch codeup master --depth 1 2>&1 || git fetch codeup master 2>&1",
            "git reset --hard codeup/master 2>&1",
            "git clean -fd 2>&1",
            "git log -1 --oneline"
        ]
        out, err, ec = ssh_exec(client, " && ".join(cmds), timeout=60)
        print(f"Git pull result: {out[:500]}")
        if ec != 0:
            print(f"Git pull error: {err[:500]}")
    else:
        git_auth_url = f"https://{GIT_USER}:{GIT_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
        cmd = f"timeout 60 git clone --depth 1 --single-branch '{git_auth_url}' {PROJECT_DIR} 2>&1"
        out, err, ec = ssh_exec(client, cmd, timeout=90)
        print(f"Git clone result: {out[:500]}")
        if ec != 0:
            print(f"Git clone error: {err[:500]}")
            # Try without timeout
            cmd2 = f"git clone --depth 1 --single-branch '{git_auth_url}' {PROJECT_DIR} 2>&1"
            out2, err2, ec2 = ssh_exec(client, cmd2, timeout=120)
            print(f"Git clone retry: {out2[:500]}")
    
    # Verify code
    out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR} && ls -la deploy/ 2>&1")
    print(f"Deploy files: {out[:500]}")
    
    # ===== Step 2: ACR login =====
    print("\n[3/10] ACR login...")
    out, err, ec = ssh_exec(client, f"docker login --username={ACR_USER} --password='{ACR_PASS}' {ACR_ADDR} 2>&1")
    print(f"ACR login: {out.strip()}")

    # ===== Step 3: Generate BUILD_COMMIT =====
    print("\n[4/10] Generate BUILD_COMMIT...")
    out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown'")
    build_commit = out.strip().replace("'", "")
    print(f"BUILD_COMMIT={build_commit}")
    
    # ===== Step 4: Docker compose build & up =====
    print("\n[5/10] Docker compose build & up...")
    cmds = [
        f"cd {PROJECT_DIR}/deploy",
        f"BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml down 2>/dev/null || true",
        f"BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml build --pull 2>&1",
    ]
    out, err, ec = ssh_exec(client, " && ".join(cmds), timeout=600)
    print(f"Build output (last 1000 chars): {out[-1000:]}")
    if ec != 0:
        print(f"Build error: {err[-1000:]}")
        print("Retrying build without --pull...")
        cmd2 = f"cd {PROJECT_DIR}/deploy && BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml build 2>&1"
        out2, err2, ec2 = ssh_exec(client, cmd2, timeout=600)
        print(f"Rebuild output (last 500): {out2[-500:]}")
    
    # Start containers
    out, err, ec = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
    print(f"Up result: {out[:500]}")
    if err.strip():
        print(f"Up errors: {err[:500]}")
    
    # ===== Step 5: Wait for health checks =====
    print("\n[6/10] Waiting for container health checks...")
    max_wait = 24
    for i in range(max_wait):
        time.sleep(5)
        out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null")
        healthy_count = out.count('"Health":"healthy"')
        total_lines = len([l for l in out.split('\n') if l.strip()])
        print(f"  [{i+1}/{max_wait}] {healthy_count}/{total_lines} healthy")
        if healthy_count >= 3:  # All 3 services healthy
            print("All containers healthy!")
            break
    else:
        print("Warning: timeout waiting for healthy containers")
        out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps 2>&1")
        print(f"Container status: {out}")
    
    # ===== Step 6: Connect gateway to project network =====
    print("\n[7/10] Connect gateway to project network...")
    out, err, ec = ssh_exec(client, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || echo 'ALREADY_CONNECTED'")
    print(f"Network connect: {out.strip()}")
    
    # ===== Step 7: Update gateway nginx config =====
    print("\n[8/10] Update gateway nginx config (nested mode)...")
    
    # Backup existing conf
    out, _, _ = ssh_exec(client, f"mkdir -p /home/ubuntu/gateway/conf.d.bak && cp {GATEWAY_CONF} /home/ubuntu/gateway/conf.d.bak/{DEPLOY_ID}.conf.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null; echo DONE")
    
    # Copy gateway-routes.conf to server
    # We need to read it from local and write to remote
    print("Copying gateway-routes.conf to server...")
    # Use Python to copy the file content
    
    # First check if server block already exists in nginx.conf
    out, _, _ = ssh_exec(client, f"grep -c 'server_name {DEPLOY_ID}.{WILDCARD_BASE}' {NGINX_CONF} 2>/dev/null || echo '0'")
    server_exists = '0' not in out.strip() and out.strip() != '0'
    
    if not server_exists:
        print("Adding server block to nginx.conf...")
        # Write a Python script to modify nginx.conf
        insert_script = f'''
import re
conf_path = "{NGINX_CONF}"
with open(conf_path, 'r') as f:
    content = f.read()

server_block = '''
    # ===== Project: {DEPLOY_ID} (auto-generated) =====
    server {{
        listen 80;
        server_name {DEPLOY_ID}.{WILDCARD_BASE};
        return 301 https://$host$request_uri;
    }}

    server {{
        listen 443 ssl http2;
        server_name {DEPLOY_ID}.{WILDCARD_BASE};
        resolver 127.0.0.11 valid=10s ipv6=off;

        ssl_certificate     /etc/nginx/ssl/wildcard.{WILDCARD_BASE}.crt;
        ssl_certificate_key /etc/nginx/ssl/wildcard.{WILDCARD_BASE}.key;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        include /etc/nginx/conf.d/{DEPLOY_ID}.conf;
    }}
'''

# Insert before the closing }} of http block
last_brace = content.rfind('}')
if last_brace > 0:
    content = content[:last_brace] + server_block + '\\n' + content[last_brace:]

with open(conf_path, 'w') as f:
    f.write(content)
print("Server block inserted into nginx.conf")
'''
        script_cmd = f"cat > /tmp/insert_server.py << 'PYEOF'\n{insert_script}\nPYEOF\npython3 /tmp/insert_server.py 2>&1 && rm /tmp/insert_server.py"
        out, err, ec = ssh_exec(client, script_cmd, timeout=30)
        print(f"Insert server block: {out[:500]}")
        if err.strip():
            print(f"Insert error: {err[:500]}")
    else:
        print("Server block already exists, skipping insert.")
    
    # Copy conf file to server 
    # Read local gateway-routes.conf
    with open('C:\\auto_output\\bnbbaijkgj\\deploy\\gateway-routes.conf', 'r') as f:
        conf_content = f.read()
    
    # Write to remote via heredoc
    escaped_content = conf_content.replace('\\', '\\\\').replace('$', '\\$').replace('`', '\\`').replace('"', '\\"')
    # Use base64 to avoid escaping issues
    import base64
    b64_content = base64.b64encode(conf_content.encode()).decode()
    cmd = f"echo '{b64_content}' | base64 -d > {GATEWAY_CONF} 2>&1 && echo 'CONF_WRITTEN'"
    out, err, ec = ssh_exec(client, cmd, timeout=15)
    print(f"Write conf: {out.strip()}")
    if err.strip():
        print(f"Write conf error: {err.strip()}")

    # ===== Step 8: Test and reload gateway =====
    print("\n[9/10] Test and reload gateway nginx...")
    out, err, ec = ssh_exec(client, "docker exec gateway-nginx nginx -t 2>&1")
    print(f"Nginx test: {out.strip()} {err.strip()}")
    
    if ec == 0:
        out, err, ec = ssh_exec(client, "docker exec gateway-nginx nginx -s reload 2>&1")
        print(f"Nginx reload: {out.strip()} {err.strip()}")
        time.sleep(2)
        # SSL connectivity test
        out, _, _ = ssh_exec(client, f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/ 2>&1 | head -10")
        print(f"HTTPS test: {out[:500]}")
    else:
        print("ERROR: nginx config test failed! Rolling back...")
        # Rollback
        ssh_exec(client, f"cp /home/ubuntu/gateway/conf.d.bak/{DEPLOY_ID}.conf.bak.* {GATEWAY_CONF} 2>/dev/null; echo ROLLBACK")
    
    # ===== Step 9: Database init / migration =====
    print("\n[10/10] Database initialization / migration...")
    
    # Check if tables exist
    out, err, ec = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"
from app.database import engine
from sqlalchemy import inspect
try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(len(tables))
    for t in sorted(tables):
        print(t)
except Exception as e:
    print(f'0')
    print(f'Error: {{e}}')
\" 2>&1", timeout=30)
    print(f"DB check: {out[:500]}")
    
    if 'Error:' in out or '0' in out.split('\n')[0]:
        print("No tables found or error - performing create_all...")
        out2, err2, ec2 = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('Tables created successfully')
\" 2>&1", timeout=30)
        print(f"Create tables: {out2[:500]} {err2[:500]}")
    else:
        print("Tables exist - running create_all for incremental update...")
        out2, err2, ec2 = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('Tables updated (existing skipped)')
\" 2>&1", timeout=30)
        print(f"Incremental update: {out2[:500]} {err2[:500]}")
    
    # ===== Step 10: Check/create default admin account =====
    print("\n[11/11] Check default admin account...")
    # Try API check
    out, err, ec = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"
import urllib.request, json
try:
    req = urllib.request.Request('http://localhost:8000/api/auth/login', 
        data=json.dumps({{'username':'admin','password':'admin123'}}).encode(),
        headers={{'Content-Type':'application/json'}},
        method='POST')
    resp = urllib.request.urlopen(req, timeout=10)
    print(f'LOGIN_OK: {{resp.status}}')
except Exception as e:
    print(f'LOGIN_FAIL: {{e}}')
\" 2>&1", timeout=20)
    print(f"Admin login test: {out.strip()[:300]}")
    
    if 'LOGIN_OK' not in out:
        print("Admin account not found or login failed - attempting to create...")
        # Try to create via direct DB insert
        out2, err2, ec2 = ssh_exec(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"
from app.database import SessionLocal
from app.models.models import User
from app.core.security import get_password_hash
import sys
try:
    db = SessionLocal()
    existing = db.query(User).filter(User.username == 'admin').first()
    if not existing:
        hashed = get_password_hash('admin123')
        user = User(username='admin', hashed_password=hashed, is_admin=True)
        db.add(user)
        db.commit()
        print('ADMIN_CREATED')
    else:
        print('ADMIN_EXISTS_BUT_LOGIN_FAILED')
    db.close()
except Exception as e:
    print(f'CREATE_ERROR: {{e}}')
\" 2>&1", timeout=20)
        print(f"Admin creation: {out2[:300]} {err2[:300]}")
    
    # ===== Final summary =====
    print("\n" + "="*60)
    print("DEPLOYMENT COMPLETE - FINAL STATUS")
    print("="*60)
    out, _, _ = ssh_exec(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps 2>&1")
    print(f"Container status:\n{out}")
    
    out, _, _ = ssh_exec(client, f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/api/health 2>&1 | head -5")
    print(f"Backend health endpoint: {out[:300]}")
    
    print(f"\nDEPLOY_ID: {DEPLOY_ID}")
    print(f"Project URL: https://{DEPLOY_ID}.{WILDCARD_BASE}")
    print(f"Admin URL: https://{DEPLOY_ID}.{WILDCARD_BASE}/admin/")
    print(f"Server: {HOST}:{PORT}")
    print(f"SSH: {USER}@{HOST}")
    
    client.close()
    return True

if __name__ == '__main__':
    try:
        run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
