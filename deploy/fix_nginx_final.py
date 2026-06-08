"""
Final nginx fix + DB init + admin account check.
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

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PASS, timeout=15)
print("Connected.", flush=True)

def run(cmd, desc=""):
    i, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode('utf-8', errors='replace')
    err = e.read().decode('utf-8', errors='replace')
    ec = o.channel.recv_exit_status()
    if desc:
        print(f"[{desc}] ec={ec}", flush=True)
    return out, err, ec

# Step 1: Upload clean script
sftp = c.open_sftp()
with open(r'C:\auto_output\bnbbaijkgj\deploy\clean_nginx.py', 'r') as f:
    sftp.putfo(f, '/tmp/clean_nginx.py')
sftp.close()
print("Uploaded clean_nginx.py", flush=True)

# Step 2: Run clean script
out, err, ec = run("python3 /tmp/clean_nginx.py", "clean_nginx")
print(f"Clean: {out.strip()}", flush=True)
print(f"Err: {err.strip()}", flush=True)

# Step 3: Test nginx
out, err, ec = run("docker exec gateway-nginx nginx -t 2>&1", "nginx_test")
# Filter important lines
important = []
for line in (out + err).split('\n'):
    low = line.lower()
    if 'success' in low or 'ok' in low or 'emerg' in low or 'error' in low or 'failed' in low:
        important.append(line)
if important:
    print(f"Nginx: {chr(10).join(important)}", flush=True)
else:
    print(f"Nginx: OK (no errors)", flush=True)

# Step 4: Reload if ok
if ec == 0:
    out, err, ec = run("docker exec gateway-nginx nginx -s reload 2>&1", "reload")
    print(f"Reload: {out.strip()} {err.strip()}", flush=True)
else:
    print("SKIP RELOAD - nginx test failed", flush=True)
    # Try to diagnose
    out, err, ec = run("grep -n '6b099ed3.*conf' /home/ubuntu/gateway/nginx.conf", "diagnose")
    print(f"Grep: {out.strip()}", flush=True)
    # Check if line causing issue
    out, err, ec = run("wc -l /home/ubuntu/gateway/nginx.conf", "wc")
    print(f"Lines: {out.strip()}", flush=True)

# Step 5: DB init
print("\n--- DB Init ---", flush=True)
out, err, ec = run(
    f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.core.database import Base, engine; "
    "from sqlalchemy import inspect; inspector = inspect(engine); "
    "tbls = inspector.get_table_names(); print(len(tbls)); "
    "[print(t) for t in sorted(tbls)]'", "db_check")
print(f"DB: {out[:500]}", flush=True)
if err:
    print(f"DB err: {err[:300]}", flush=True)

if out.strip() == '0' or 'Error' in out:
    out2, err2, ec2 = run(
        f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.core.database import Base, engine; "
        "Base.metadata.create_all(bind=engine); print(\"CREATED\")'", "db_create")
    print(f"Create: {out2[:300]} {err2[:300]}", flush=True)
else:
    out2, err2, ec2 = run(
        f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.core.database import Base, engine; "
        "Base.metadata.create_all(bind=engine); print(\"UPDATED\")'", "db_update")
    print(f"Update: {out2[:300]} {err2[:300]}", flush=True)

# Step 6: Admin account
print("\n--- Admin Account ---", flush=True)
out, err, ec = run(
    f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.core.database import SessionLocal; "
    "from app.models.models import User; db=SessionLocal(); "
    "u=db.query(User).filter(User.username==\"admin\").first(); "
    "print(\"EXISTS\" if u else \"NOT_FOUND\"); db.close()'", "admin_check")
print(f"Admin: {out.strip()}", flush=True)

if 'NOT_FOUND' in out:
    out2, err2, ec2 = run(
        f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.core.database import SessionLocal; "
        "from app.models.models import User; from app.core.security import get_password_hash; "
        "db=SessionLocal(); u=User(username=\"admin\", hashed_password=get_password_hash(\"admin123\"), "
        "is_admin=True); db.add(u); db.commit(); print(\"ADMIN_CREATED\"); db.close()'", "admin_create")
    print(f"Create admin: {out2[:300]} {err2[:300]}", flush=True)

# Step 7: HTTPS test
print("\n--- HTTPS Test ---", flush=True)
time.sleep(2)
out, err, ec = run(f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/ 2>&1 | head -5", "https_h5")
print(f"H5: {out[:300]}", flush=True)

out, err, ec = run(f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/api/health 2>&1 | head -5", "https_api")
print(f"API: {out[:300]}", flush=True)

out, err, ec = run(f"curl -sI -k https://{DEPLOY_ID}.{WILDCARD_BASE}/admin/ 2>&1 | head -5", "https_admin")
print(f"Admin: {out[:300]}", flush=True)

# Step 8: Container status
print("\n--- Containers ---", flush=True)
out, err, ec = run(f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'", "containers")
print(out, flush=True)

print("\n=== FINAL STATUS ===", flush=True)
print(f"DEPLOY_ID: {DEPLOY_ID}", flush=True)
print(f"URL: https://{DEPLOY_ID}.{WILDCARD_BASE}", flush=True)
print(f"Admin: https://{DEPLOY_ID}.{WILDCARD_BASE}/admin/", flush=True)

c.close()
