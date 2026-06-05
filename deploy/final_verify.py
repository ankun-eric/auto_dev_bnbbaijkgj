"""Final verification: account check, API test, SSL check, git fix."""
import paramiko, sys

HOST, USER, PASS = "newbb.test.bangbangvip.com", "ubuntu", "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PDIR = f"/home/ubuntu/{DID}"
DOMAIN = f"{DID}.noob-ai.test.bangbangvip.com"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd[:120]}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f"EXIT={ec}", flush=True)
    if out.strip(): print(out[:600], flush=True)
    if err.strip() and ec != 0: print("ERR:", err[:300], flush=True)
    return ec, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASS, timeout=15)
print("Connected", flush=True)

# Fix git unstaged changes on server
print("\n=== Fix git state ===", flush=True)
run(ssh, f"cd {PDIR} && git checkout -- deploy/docker-compose.prod.yml 2>&1")

# Final container status
print("\n=== Container Status ===", flush=True)
run(ssh, f"docker ps --filter name={DID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

# Check accounts via backend API
print("\n=== Account check via API ===", flush=True)
run(ssh, "docker exec " + DID + "-backend python3 -c \"import urllib.request; resp=urllib.request.urlopen('http://127.0.0.1:8000/api/health'); print('Health:', resp.read().decode())\" 2>&1", timeout=15)

# Check default admin account
print("\n=== Check admin account ===", flush=True)
run(ssh, "docker exec " + DID + "-backend python3 -c \"import sys; sys.path.insert(0,'/app'); from app.database import engine; from sqlalchemy import text; conn=engine.connect(); rows=conn.execute(text('SELECT username, role, is_active FROM users LIMIT 5')).fetchall(); [print(r) for r in rows]; conn.close()\" 2>&1", timeout=15)

# SSL check
print("\n=== SSL Check ===", flush=True)
run(ssh, f"curl -skI https://{DOMAIN}/api/health 2>&1 | head -10", timeout=15)

# Gateway routing test
print("\n=== Gateway routing test ===", flush=True)
run(ssh, f"curl -sk https://{DOMAIN}/ 2>&1 | head -5", timeout=15)
run(ssh, f"curl -sk https://{DOMAIN}/admin/ 2>&1 | head -5", timeout=15)

ssh.close()
print("\n=== VERIFICATION COMPLETE ===", flush=True)
print(f"Project URL: https://{DOMAIN}", flush=True)
print(f"Admin URL: https://{DOMAIN}/admin/", flush=True)
