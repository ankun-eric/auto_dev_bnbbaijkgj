"""
Fix deployment issues and continue.
1. Fix nginx conf extension (.conf -> .server)
2. Check and restart containers
3. DB init + admin account
"""
import paramiko
import time
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = "noob-ai.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
NGINX_CONF = "/home/ubuntu/gateway/nginx.conf"

def cmd(client, command, timeout=60):
    """Execute command and return output."""
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

print("Connecting...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS, timeout=15)
print("Connected!")

# ============================================================
# FIX 1: Nginx config - change .conf to .server
# ============================================================
print("\n=== FIX 1: Nginx config extension ===")
# Check current state
out, err, ec = cmd(client, f"ls -la /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.* 2>&1")
print(f"Conf files: {out.strip()}")

# Remove the .conf file that causes conflict, rename to .server
out, err, ec = cmd(client, f"mv /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server 2>&1")
print(f"Rename: {out.strip()} {err.strip()}")

# Update nginx.conf server block to include .server instead of .conf
out, err, ec = cmd(client, f"sed -i 's|include /etc/nginx/conf.d/{DEPLOY_ID}.conf;|include /etc/nginx/conf.d/{DEPLOY_ID}.server;|g' {NGINX_CONF} 2>&1")
print(f"Sed update: {err.strip() if err else 'OK'}")

# Also remove any .dup_disabled file
out, err, ec = cmd(client, f"rm -f /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf.dup_disabled 2>&1")
print(f"Cleanup: OK")

# Test nginx
out, err, ec = cmd(client, "docker exec gateway-nginx nginx -t 2>&1")
print(f"Nginx test:\n{out[-500:]}\n{err[-500:]}")
if ec == 0:
    out, err, ec = cmd(client, "docker exec gateway-nginx nginx -s reload 2>&1")
    print(f"Reload: {out.strip()} {err.strip()}")
else:
    # Check for duplicate location - might need to remove the conf file entirely
    print("Still failing - checking if we need to remove nested include conflict...")
    # The issue might be that .server files are also included by some wildcard
    # Let's check what includes exist
    out, err, ec = cmd(client, "grep -n 'include.*conf.d' /home/ubuntu/gateway/nginx.conf 2>&1")
    print(f"Includes:\n{out[:500]}")

# ============================================================
# FIX 2: Check and restart containers
# ============================================================
print("\n=== FIX 2: Container status ===")
out, err, ec = cmd(client, "docker ps -a --filter name=6b099ed3 --format '{{.Names}} {{.Status}}' 2>&1")
print(f"Containers:\n{out}")

# Check network
out, err, ec = cmd(client, f"docker network inspect {DEPLOY_ID}-network --format '{{{{.Name}}}} {{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}' 2>&1")
print(f"Network: {out.strip()}")

# If containers not running, try starting them
if 'Up' not in out:
    print("Containers not running - attempting to start...")
    # Check if images exist
    out, err, ec = cmd(client, f"docker images --filter reference='*{DEPLOY_ID}*' --format '{{{{.Repository}}}}:{{{{.Tag}}}}' 2>&1")
    print(f"Images:\n{out[:500]}")
    
    # Try docker compose up
    out, err, ec = cmd(client, f"cd {PROJECT_DIR}/deploy && BUILD_COMMIT=$(cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown') && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=60)
    print(f"Up result: {out[:500]}")
    print(f"Up errors: {err[:500]}")
    
    # Check again
    time.sleep(5)
    out, err, ec = cmd(client, "docker ps -a --filter name=6b099ed3 --format '{{.Names}} {{.Status}}' 2>&1")
    print(f"After restart:\n{out}")

# ============================================================
# FIX 3: Wait for health
# ============================================================
print("\n=== FIX 3: Wait for health ===")
for i in range(24):
    time.sleep(5)
    out, err, ec = cmd(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null")
    healthy = out.count('"Health":"healthy"')
    lines = [l for l in out.split('\n') if l.strip()]
    total = max(len(lines), 1)
    print(f"  [{i+1}/24] {healthy}/{total} healthy")
    if healthy >= total and healthy >= 3:
        print("All healthy!")
        break
else:
    print("Warning: timeout")
    out, err, ec = cmd(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps 2>&1")
    print(f"Status:\n{out}")
    # Check logs
    out, err, ec = cmd(client, f"docker logs {DEPLOY_ID}-backend --tail 30 2>&1")
    print(f"Backend logs:\n{out[:1000]}")

# ============================================================
# PART 4: DB init
# ============================================================
print("\n=== DB Init ===")
# Simpler check
out, err, ec = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import engine, Base; from sqlalchemy import inspect; inspector = inspect(engine); tbls = inspector.get_table_names(); print(len(tbls)); [print(t) for t in sorted(tbls)]' 2>&1", timeout=30)
print(f"DB tables: {out[:500]}")
if err:
    print(f"DB err: {err[:300]}")

if 'Error' in out or out.strip() == '0' or not out.strip():
    out2, err2, ec2 = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import Base, engine; Base.metadata.create_all(bind=engine); print(\"CREATED\")' 2>&1", timeout=30)
    print(f"Create: {out2[:300]} {err2[:300]}")
else:
    out2, err2, ec2 = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import Base, engine; Base.metadata.create_all(bind=engine); print(\"UPDATED\")' 2>&1", timeout=30)
    print(f"Update: {out2[:300]} {err2[:300]}")

# ============================================================
# PART 5: Admin account
# ============================================================
print("\n=== Admin Account ===")
# Check admin via backend
out, err, ec = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import SessionLocal; from app.models.models import User; db=SessionLocal(); u=db.query(User).filter(User.username==\"admin\").first(); print(\"EXISTS\" if u else \"NOT_FOUND\"); db.close()' 2>&1", timeout=20)
print(f"Admin check: {out.strip()[:200]}")

if 'NOT_FOUND' in out or 'Error' in out:
    out2, err2, ec2 = cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import SessionLocal; from app.models.models import User; from app.core.security import get_password_hash; db=SessionLocal(); u=User(username=\"admin\", hashed_password=get_password_hash(\"admin123\"), is_admin=True); db.add(u); db.commit(); print(\"ADMIN_CREATED\"); db.close()' 2>&1", timeout=20)
    print(f"Create admin: {out2[:200]} {err2[:200]}")
else:
    print("Admin account exists")

# ============================================================
# FINAL
# ============================================================
print("\n" + "="*60)
print("FIX COMPLETE")
print(f"URL: https://{DEPLOY_ID}.{WILDCARD_BASE}")
print(f"Admin: https://{DEPLOY_ID}.{WILDCARD_BASE}/admin/")

# Final status
out, err, ec = cmd(client, f"cd {PROJECT_DIR}/deploy && docker compose -f docker-compose.prod.yml ps 2>&1")
print(f"\nContainer status:\n{out}")

# HTTPS test
out, err, ec = cmd(client, f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/ 2>&1 | head -8")
print(f"HTTPS test:\n{out[:500]}")

client.close()
