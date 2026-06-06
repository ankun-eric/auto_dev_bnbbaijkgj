"""Post-deploy fixes v2: DB migration + admin account + gateway verification."""
import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"

OUT_FILE = "C:/auto_output/bnbbaijkgj/fix_final_out.txt"

def log(msg):
    print(msg)
    with open(OUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def run(ssh, cmd, timeout=30):
    log(f"CMD: {cmd[:150]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        log(f"OUT: {out[:600]}")
    if err:
        log(f"ERR: {err[:600]}")
    return out, err

open(OUT_FILE, "w").close()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=20)
log("SSH connected")

# 1. Check DB tables via API
log("\n=== 1. DB Migration Check ===")
# Use python3 to call the health API first
run(ssh, f'docker exec {DEPLOY_ID}-backend python3 -c "import urllib.request; r=urllib.request.urlopen(\'http://localhost:8000/api/health\'); print(r.status, r.read().decode()[:200])"')

# Check if main.py has auto-migration (create_all)
log("\n=== 1b. Check main.py for auto init ===")
out, _ = run(ssh, f'docker exec {DEPLOY_ID}-backend grep -n "create_all\|Base.metadata\|init_db\|_migrate" /app/app/main.py')

# Try async DB check
check_db = f'''docker exec {DEPLOY_ID}-backend python3 -c "
import asyncio
from app.core.database import engine, Base

async def check():
    async with engine.begin() as conn:
        from sqlalchemy import inspect
        def sync_check(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            print(f'Tables: {{len(tables)}} - {{tables[:15]}}')
        await conn.run_sync(sync_check)

asyncio.run(check())
"'''
out, err = run(ssh, check_db)

# If tables exist, run create_all for new tables
if 'Tables:' in out and '0' not in out.split('Tables:')[1].split('-')[0].strip():
    log("  Tables exist, running create_all for any new tables...")
    run(ssh, f'''docker exec {DEPLOY_ID}-backend python3 -c "
import asyncio
from app.core.database import engine, Base

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('create_all done')

asyncio.run(migrate())
"''')
else:
    log("  No tables found or error, checking if main.py handles init...")
    # Try restarting backend to trigger auto-migration
    log("  Backend may handle init on startup, checking logs...")
    out, _ = run(ssh, f'docker logs --tail 30 {DEPLOY_ID}-backend')

# 2. Admin account via python3
log("\n=== 2. Admin Account Check ===")
check_admin = f'''docker exec {DEPLOY_ID}-backend python3 -c "
import urllib.request, json
data = json.dumps({{'username':'admin','password':'admin123'}}).encode()
req = urllib.request.Request('http://localhost:8000/api/auth/login', data=data, headers={{'Content-Type':'application/json'}})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    body = resp.read().decode()
    print(f'Login: status={{resp.status}} body={{body[:200]}}')
except Exception as e:
    print(f'Login error: {{e}}')
"'''
out, err = run(ssh, check_admin)

if 'access_token' not in out and 'Login error' not in out:
    log("  Creating admin account...")
    create_admin = f'''docker exec {DEPLOY_ID}-backend python3 -c "
import urllib.request, json
data = json.dumps({{'username':'admin','password':'admin123','nickname':'Admin','phone':'13800000000'}}).encode()
req = urllib.request.Request('http://localhost:8000/api/auth/register', data=data, headers={{'Content-Type':'application/json'}})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(f'Register: status={{resp.status}} body={{resp.read().decode()[:200]}}')
except Exception as e:
    print(f'Register error: {{e}}')
"'''
    run(ssh, create_admin)

# 3. Gateway check
log("\n=== 3. Gateway Verification ===")
run(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/")
run(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health")
run(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/admin/")

# 4. Container status
log("\n=== 4. Container Status ===")
out, _ = run(ssh, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'")

log("\n=== Fix Complete ===")
ssh.close()
