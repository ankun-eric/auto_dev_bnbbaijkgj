#!/usr/bin/env python3
"""Verify backend after database fix"""
import paramiko, time, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, timeout=30):
    print('\n[CMD] ' + cmd[:180])
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        print('[OUT] ' + out.strip()[:900])
    if err.strip():
        print('[ERR] ' + err.strip()[:400])
    sys.stdout.flush()
    return out, err

domain = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

print("=" * 60)
print("Waiting 40s for backend startup...")
print("=" * 60)
time.sleep(40)

print("\n=== CONTAINER STATUS ===")
run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")

print("\n=== BACKEND LOGS (last 50) ===")
run("docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --tail 50 2>&1")

print("\n=== HTTP CHECKS ===")
run("curl -sk -w '\\nHTTP_CODE:%{http_code}\\n' https://" + domain + "/api/health")
run("curl -sk -w '\\nHTTP_CODE:%{http_code}\\n' https://" + domain + "/")
run("curl -sk -w '\\nHTTP_CODE:%{http_code}\\n' https://" + domain + "/admin/")

# If API still failing, check if noob_ai-db has bini_health db
print("\n=== CHECK DATABASE EXISTENCE ===")
# Use a temporary container to check MySQL
run("docker run --rm --network 6b099ed3-7175-4a78-91f4-44570c84ed27-network mysql:8.0 mysql -h noob_ai-db -u root -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1 | head -20")

ssh.close()
print("\nDone!")
