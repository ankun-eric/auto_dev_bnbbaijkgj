#!/usr/bin/env python3
import paramiko, sys
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd):
    print(f"\n>>> {cmd[:140]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60, get_pty=True)
    out = stdout.read().decode("utf-8", "replace")
    print(out)
    return out

# 容器状态
run(f"docker ps -a --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID}")

# backend 日志
run(f"docker logs --tail 200 {PROJECT_ID}-backend 2>&1 | tail -100")

ssh.close()
