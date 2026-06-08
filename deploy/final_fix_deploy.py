"""
Final fix: stop old containers, restart with new code, fix nginx.
"""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = "noob-ai.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
NGINX_CONF = "/home/ubuntu/gateway/nginx.conf"
SERVER_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server"

def cmd(client, command, timeout=60):
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    ec = stdout.channel.recv_exit_status()
    return out, err, ec

print("Connecting...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS, timeout=15)
print("Connected!")

# Step 1: Stop old containers forcefully
print("\n=== Step 1: Stop old containers ===")
# Stop by container name directly
for svc in ['admin', 'h5', 'backend']:
    cname = f"{DEPLOY_ID}-{svc}"
    out, err, ec = cmd(client, f"docker stop {cname} 2>&1 || true")
    out2, err2, ec2 = cmd(client, f"docker rm {cname} 2>&1 || true")
    print(f"  {cname}: stop={out.strip()[:50]} rm={out2.strip()[:50]}")

# Step 2: Start new containers with compose
print("\n=== Step 2: Start new containers ===")
build_commit_cmd = f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown'"
out, _, _ = cmd(client, build_commit_cmd)
build_commit = out.strip().replace("'", "")
print(f"BUILD_COMMIT={build_commit}")

# docker compose up
out, err, ec = cmd(client, 
    f"cd {PROJECT_DIR}/deploy && BUILD_COMMIT='{build_commit}' docker compose -f docker-compose.prod.yml up -d 2>&1",
    timeout=120)
print(f"Up: {out[:500]}")
if err:
    print(f"Errors: {err[:500]}")

# Wait for health
print("\n=== Step 3: Wait for health ===")
for i in range(36):
    time.sleep(5)
    out, _, _ = cmd(client, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}' 2>&1")
    lines = [l for l in out.split('\n') if l.strip()]
    healthy = sum(1 for l in lines if 'healthy' in l.lower())
    print(f"  [{i+1}/36] {healthy}/{len(lines)} healthy: {lines}")
    if healthy >= 3 and len(lines) >= 3:
        print("All healthy!")
        break

# Step 4: Fix nginx .server file
print("\n=== Step 4: Fix nginx server config ===")
# Create a proper server block config
server_conf = f"""# ===== Project: {DEPLOY_ID} (auto-generated) =====
server {{
    listen 443 ssl;
    server_name {DEPLOY_ID}.{WILDCARD_BASE};
    resolver 127.0.0.11 valid=10s ipv6=off;

    ssl_certificate     /etc/nginx/ssl/wildcard.{WILDCARD_BASE}.crt;
    ssl_certificate_key /etc/nginx/ssl/wildcard.{WILDCARD_BASE}.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    location /api/ {{
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
        set $backend {DEPLOY_ID}-backend;
        proxy_pass http://$backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        expires 30d;
        add_header Cache-Control "public" always;
    }}

    location /admin/ {{
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

# Remove old nginx.conf explicit include and inserted server block
# First, remove any previously inserted server blocks for our project
out, _, _ = cmd(client, f"grep -n 'Project: {DEPLOY_ID}' {NGINX_CONF} 2>/dev/null")
print(f"Existing server blocks: {out.strip()[:300]}")

# Remove our explicit include line
out, _, _ = cmd(client, f"sed -i '/include \\/etc\\/nginx\\/conf.d\\/{DEPLOY_ID}.server;/d' {NGINX_CONF} 2>&1")
print("Removed explicit include")

# Remove any auto-generated server blocks from nginx.conf
cmd_remove = f"""python3 -c "
content = open('{NGINX_CONF}').read()
# Remove our auto-generated server block
import re
pattern = r'    # ===== Project: {DEPLOY_ID} \(auto-generated\) =====.*?\n    server \\{{\\n        listen 443.*?\\n    \\}}\\n'
content = re.sub(pattern, '', content, flags=re.DOTALL)
# Also remove the port 80 redirect block
pattern2 = r'    # ===== Project: {DEPLOY_ID} \(auto-generated\) =====.*?\n    server \\{{\\n        listen 80.*?\\n    \\}}\\n'
content = re.sub(pattern2, '', content, flags=re.DOTALL)
open('{NGINX_CONF}','w').write(content)
print('Cleaned nginx.conf')
" 2>&1"""
out, err, ec = cmd(client, cmd_remove, timeout=15)
print(f"Clean nginx.conf: {out.strip()} {err.strip()[:200]}")

# Write the server conf file using base64 (to avoid escaping issues)
import base64
b64 = base64.b64encode(server_conf.encode()).decode()
out, err, ec = cmd(client, f"echo '{b64}' | base64 -d > {SERVER_CONF} && echo 'WRITTEN' 2>&1")
print(f"Write server conf: {out.strip()}")

# Test nginx
out, err, ec = cmd(client, "docker exec gateway-nginx nginx -t 2>&1")
print(f"\nNginx test:\n{out.strip()[-500:]}")
if err.strip():
    err_lines = [l for l in err.strip().split('\n') if 'warn' not in l.lower()]
    if err_lines:
        print(f"Nginx errors: {chr(10).join(err_lines[-5:])}")

if ec == 0:
    out, err, ec = cmd(client, "docker exec gateway-nginx nginx -s reload 2>&1")
    print(f"Reload: {out.strip()} {err.strip()}")
    time.sleep(2)
    
    # HTTPS test
    out, _, _ = cmd(client, f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/api/health 2>&1")
    print(f"HTTPS /api/health: {out.strip()[:300]}")
    
    out, _, _ = cmd(client, f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/ 2>&1")
    print(f"HTTPS /: {out.strip()[:300]}")
    
    out, _, _ = cmd(client, f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/admin/ 2>&1")
    print(f"HTTPS /admin/: {out.strip()[:300]}")
else:
    print("Nginx test FAILED, keeping old config")
    # Restore old server file if it existed
    out, _, _ = cmd(client, f"ls -t /home/ubuntu/gateway/conf.d.bak/{DEPLOY_ID}.* 2>/dev/null | head -1")
    if out.strip():
        cmd(client, f"cp {out.strip()} {SERVER_CONF} 2>&1")
        print(f"Restored from backup: {out.strip()}")

# Step 5: DB Init
print("\n=== Step 5: DB Init ===")
out, err, ec = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import Base, engine; from sqlalchemy import inspect; inspector = inspect(engine); tbls = inspector.get_table_names(); print(len(tbls)); [print(t) for t in sorted(tbls)]' 2>&1", timeout=30)
print(f"Tables: {out[:500]}")
if err:
    print(f"DB err: {err[:300]}")

if 'Error' in out or out.strip() == '0' or not out.strip():
    out2, _, _ = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import Base, engine; Base.metadata.create_all(bind=engine); print(\"CREATED\")' 2>&1")
    print(f"DB Create: {out2[:300]}")
else:
    out2, _, _ = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import Base, engine; Base.metadata.create_all(bind=engine); print(\"UPDATED\")' 2>&1")
    print(f"DB Update: {out2[:300]}")

# Step 6: Admin account
print("\n=== Step 6: Admin account ===")
out, err, ec = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import SessionLocal; from app.models.models import User; db=SessionLocal(); u=db.query(User).filter(User.username==\"admin\").first(); print(\"EXISTS\" if u else \"NOT_FOUND\"); db.close()' 2>&1")
print(f"Admin: {out.strip()[:200]}")
if err:
    print(f"Admin err: {err.strip()[:200]}")

if 'NOT_FOUND' in out:
    out2, _, _ = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import SessionLocal; from app.models.models import User; from app.core.security import get_password_hash; db=SessionLocal(); u=User(username=\"admin\", hashed_password=get_password_hash(\"admin123\"), is_admin=True); db.add(u); db.commit(); print(\"ADMIN_CREATED\"); db.close()' 2>&1")
    print(f"Create: {out2[:200]}")

# Final
print("\n" + "="*60)
print("DEPLOYMENT COMPLETE")
print(f"DEPLOY_ID: {DEPLOY_ID}")
print(f"URL: https://{DEPLOY_ID}.{WILDCARD_BASE}")
print(f"Admin: https://{DEPLOY_ID}.{WILDCARD_BASE}/admin/")
print(f"SSH: ssh {USER}@{HOST}")

out, _, _ = cmd(client, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}' 2>&1")
print(f"\nContainers:\n{out}")

client.close()
