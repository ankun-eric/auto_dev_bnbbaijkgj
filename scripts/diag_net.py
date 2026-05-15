#!/usr/bin/env python3
"""检查网络情况"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

cmds = [
    "docker network ls | grep -i 6b099ed3 || true",
    f"docker inspect {DEPLOY_ID}-db --format '{{{{json .NetworkSettings.Networks}}}}'",
    f"docker inspect {DEPLOY_ID}-backend --format '{{{{json .NetworkSettings.Networks}}}}'",
    f"docker exec {DEPLOY_ID}-backend nslookup {DEPLOY_ID}-db 2>&1 || true",
    f"docker exec {DEPLOY_ID}-backend cat /etc/hosts 2>&1 || true",
    f"docker exec {DEPLOY_ID}-backend env | grep -i database",
]
for cmd in cmds:
    print(f"\n========= $ {cmd[:120]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("[err]", err)
c.close()
