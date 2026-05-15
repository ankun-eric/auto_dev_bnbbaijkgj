#!/usr/bin/env python3
"""读取项目 nginx 配置"""
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
    print(out)

run(f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf")
run(f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}-toplevel-apk.conf")

c.close()
