#!/usr/bin/env python3
"""探测 nginx 配置（gateway 容器名）"""
import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd, t=30):
    print(f"\n$ {cmd[:140]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", errors="replace")
    print(out[:4000])

run("docker exec gateway ls /etc/nginx/conf.d/ 2>&1")
run(f"docker exec gateway grep -B 2 -A 8 '{DEPLOY_ID}' /etc/nginx/conf.d/*.conf 2>&1 | head -100")
run("docker exec gateway grep -B 1 -A 5 'autodev' /etc/nginx/conf.d/*.conf 2>&1 | head -60")

c.close()
