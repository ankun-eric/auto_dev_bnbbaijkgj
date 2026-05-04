#!/usr/bin/env python3
"""Inspect server: find the right APK directory."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=60)

cmds = [
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ 2>&1 | head -50",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/ 2>&1 | head -20",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/ 2>&1",
    "find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 -maxdepth 3 -type d -name apk 2>/dev/null",
]
for cmd in cmds:
    print(f"\n$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err:
        print("ERR:", err)
c.close()
