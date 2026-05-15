#!/usr/bin/env python3
import paramiko, sys
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
            allow_agent=False, look_for_keys=False)
def run(cmd, timeout=120):
    print(f">>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out)
    if err.strip(): print("[err]", err[:600])

# 看错误
run(f"docker logs {PROJECT_ID}-backend --tail 200 2>&1 | grep -E 'ERROR|Error|Traceback|500|health' -A 20 | tail -120")
# 直接打到容器内本地 8000
run(f"docker exec {PROJECT_ID}-backend curl -s -o - http://localhost:8000/api/health-self-check/dict | head -40")
run(f"docker exec {PROJECT_ID}-backend curl -s -o - 'http://localhost:8000/api/function-buttons?is_enabled=true' | head -60")
ssh.close()
