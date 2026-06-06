#!/usr/bin/env python3
"""Check server gateway config and project state."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

# 1. Check the active server config content
print("===== Active gateway config (.server) =====")
out, err = run(f"docker exec gateway-nginx cat /etc/nginx/conf.d/{DEPLOY_ID}.server 2>/dev/null")
print(out[:3000])

# 2. Check disabled configs
print("\n===== Disabled/dup configs =====")
out, err = run(f"docker exec gateway-nginx ls -la /etc/nginx/conf.d/ | grep {DEPLOY_ID[:8]}")
print(out)

# 3. Check project dir on server
print("\n===== Project directory on server =====")
out, err = run(f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>/dev/null")
print(out)

# 4. Check docker-compose.prod.yml on server
print("\n===== docker-compose.prod.yml on server =====")
out, err = run(f"cat /home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml 2>/dev/null")
print(out[:3000])

# 5. Check git status on server
print("\n===== Git status on server =====")
out, err = run(f"cd /home/ubuntu/{DEPLOY_ID} && git log --oneline -3 2>/dev/null")
print(out)

# 6. Check backend health
print("\n===== Backend health =====")
out, err = run(f"docker exec {DEPLOY_ID}-backend python3 -c \"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read())\" 2>/dev/null")
print(out[:500])

# 7. Check if db is shared or project-specific
print("\n===== DB container details =====")
out, err = run(f"docker inspect {DEPLOY_ID}-db --format '{{{{.NetworkSettings.Networks}}}}' 2>/dev/null")
print(out[:500])

ssh.close()
