#!/usr/bin/env python3
"""探测 nginx 静态目录"""
import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd, t=30):
    print(f"\n$ {cmd[:120]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", errors="replace")
    print(out[:3000])

run(f"ls -la /var/www/autodev/{DEPLOY_ID}/ 2>/dev/null | head -20")
run("docker ps --format '{{.Names}}' | grep -iE 'nginx|gateway'")
run("docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null || docker exec autodev-gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null")
run(f"docker exec gateway-nginx grep -A 2 '{DEPLOY_ID}' /etc/nginx/conf.d/*.conf 2>/dev/null | head -80 || docker exec autodev-gateway-nginx grep -A 2 '{DEPLOY_ID}' /etc/nginx/conf.d/*.conf 2>/dev/null | head -80")

c.close()
