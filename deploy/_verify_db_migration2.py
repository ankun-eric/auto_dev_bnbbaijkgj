#!/usr/bin/env python3
"""Verify DB migration - try multiple password options."""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def sh(cmd):
    print(f">>> {cmd[:160]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(f"[stderr] {err.strip()[:300]}")
    return out

# 从容器环境变量取 MYSQL_ROOT_PASSWORD
DB_CONTAINER = f"{PROJECT_ID}-db"
sh(f"docker exec {DB_CONTAINER} sh -c 'echo MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD'")
sh(f"docker inspect {DB_CONTAINER} | grep -iE 'MYSQL_|PASSWORD' | head -10")

# 从 backend 容器拿到正确的 DB 凭据
BACKEND = f"{PROJECT_ID}-backend"
sh(f"docker exec {BACKEND} sh -c 'env | grep -iE \"MYSQL|DB_|DATABASE\"'")

# 用 backend 看到的 user/password 来连接
ssh.close()
