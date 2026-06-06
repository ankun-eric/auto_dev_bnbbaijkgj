#!/usr/bin/env python3
"""Fix database migration and admin account."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"
DB = f"{DEPLOY_ID}-db"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
print("[OK] Connected.")

def run(cmd, timeout=60):
    print(f"\n[CMD] {cmd[:150]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    rc = stdout.channel.recv_exit_status()
    if out:
        print(f"[OUT] {out[:500]}")
    if err:
        print(f"[ERR] {err[:300]}")
    return out, err, rc

# Step 1: Check existing admin users
print("\n===== Check admin users =====")
out, err, rc = run(
    f"docker exec {DB} mysql -uroot -pbini_health_2026 bini_health "
    f"-e \"SELECT id, phone, nickname, role, is_superuser FROM users WHERE role='admin' OR is_superuser=1 LIMIT 5;\" 2>&1"
)

# Step 2: Run init_default_data from backend
print("\n===== Run init_default_data =====")
out, err, rc = run(
    f"docker exec {BACKEND} python3 -c \""
    f"import asyncio; from app.init_data import init_default_data; "
    f"asyncio.run(init_default_data()); print('INIT_DONE')\" 2>&1",
    timeout=120
)

# Step 3: Verify tables exist
print("\n===== Verify tables =====")
out, err, rc = run(
    f"docker exec {DB} mysql -uroot -pbini_health_2026 bini_health "
    f"-e \"SHOW TABLES;\" 2>&1"
)

# Step 4: Check admin again
print("\n===== Final admin check =====")
out, err, rc = run(
    f"docker exec {DB} mysql -uroot -pbini_health_2026 bini_health "
    f"-e \"SELECT id, phone, nickname, role FROM users WHERE role='admin' LIMIT 3;\" 2>&1"
)

# Step 5: Verify backend health via API
print("\n===== Backend API test =====")
out, err, rc = run(
    f"docker exec {BACKEND} python3 -c \""
    f"import urllib.request; r=urllib.request.urlopen('http://localhost:8000/api/health'); "
    f"print(r.read().decode())\" 2>&1"
)

ssh.close()
print("\n[DONE]")
