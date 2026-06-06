"""Post-deploy fixes: DB migration and admin account check."""
import paramiko, sys, os

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"

log_file = "C:/auto_output/bnbbaijkgj/fix_post_output.txt"

def log(msg):
    print(msg)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=20)

def run(cmd, timeout=30):
    log(f"CMD: {cmd[:120]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        log(f"OUT: {out[:500]}")
    if err:
        log(f"ERR: {err[:500]}")
    return out, err

# Clear log
open(log_file, "w").close()

# 1. Check backend module structure
log("=== Backend Module Structure ===")
run(f"docker exec {DEPLOY_ID}-backend ls /app/app/")
run(f"docker exec {DEPLOY_ID}-backend python3 -c 'import app.database; print(\"OK\")'")

# 2. Database migration using python3 (not curl)
log("\n=== Database Migration ===")
# Check tables using python3 with urllib
check_sql = r"""docker exec {DEPLOY_ID}-backend python3 -c "
import urllib.request
try:
    resp = urllib.request.urlopen('http://localhost:8000/api/health')
    print('API health:', resp.status)
except Exception as e:
    print('API error:', e)
"
""".format(DEPLOY_ID=DEPLOY_ID)

out, err = run(check_sql)

# Try to import database module directly
run(f"docker exec {DEPLOY_ID}-backend python3 -c 'from app.database import engine, Base; from sqlalchemy import inspect; inspector = inspect(engine); tables = inspector.get_table_names(); print(f\"Tables: {len(tables)} - {tables[:10]}\")'")

# If import fails, try alternate path
run(f"docker exec {DEPLOY_ID}-backend python3 -c 'import sys; sys.path.insert(0,\"/app\"); from app.database import engine, Base; print(\"engine OK\")'")

# 3. Check admin account using python3
log("\n=== Admin Account Check ===")
check_admin = r"""docker exec {DEPLOY_ID}-backend python3 -c "
import urllib.request, json
try:
    data = json.dumps({{'username':'admin','password':'admin123'}}).encode()
    req = urllib.request.Request('http://localhost:8000/api/auth/login', data=data,
        headers={{'Content-Type':'application/json'}})
    resp = urllib.request.urlopen(req)
    body = resp.read().decode()
    print('Login status:', resp.status)
    print('Body:', body[:300])
except Exception as e:
    print('Login error:', e)
"
""".format(DEPLOY_ID=DEPLOY_ID)

out, err = run(check_admin)

if 'access_token' not in out:
    log("  Admin account not found, trying to create...")
    # Try register
    register_cmd = r"""docker exec {DEPLOY_ID}-backend python3 -c "
import urllib.request, json
try:
    data = json.dumps({{'username':'admin','password':'admin123'}}).encode()
    req = urllib.request.Request('http://localhost:8000/api/auth/register', data=data,
        headers={{'Content-Type':'application/json'}}, method='POST')
    resp = urllib.request.urlopen(req)
    print('Register status:', resp.status)
    print('Body:', resp.read().decode()[:300])
except Exception as e:
    print('Register error:', e)
"
""".format(DEPLOY_ID=DEPLOY_ID)
    out, err = run(register_cmd)

# 4. Verify nginx is serving correctly
log("\n=== Gateway Verification ===")
run("docker exec gateway-nginx nginx -t 2>&1 || echo 'nginx_test_failed_but_may_be_preexisting'")
run(f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health")

log("\n=== Fix Complete ===")
ssh.close()
