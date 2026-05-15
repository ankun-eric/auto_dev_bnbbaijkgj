#!/usr/bin/env python3
"""快速查 backend 容器最近 200 行日志。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
_, out, _ = c.exec_command(f"docker logs --tail 200 {DEPLOY_ID}-backend 2>&1", timeout=30)
print(out.read().decode("utf-8", errors="replace"))
c.close()
