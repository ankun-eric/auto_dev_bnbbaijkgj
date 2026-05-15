#!/usr/bin/env python3
"""探测服务器静态文件目录"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

cmds = [
    f"ls -la /var/www 2>/dev/null | head -20",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/ | head -20",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/uploads 2>/dev/null | head -10",
    # 找已上传的产物
    f"find /home/ubuntu -name '*.apk' -mtime -30 -type f 2>/dev/null | head -10",
    f"find /home/ubuntu -name 'miniprogram_*.zip' -mtime -30 -type f 2>/dev/null | head -10",
    # 看 gateway-nginx 配置
    "docker exec gateway-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -40 || cat /etc/nginx/sites-enabled/* 2>/dev/null | head -60 || echo 'no nginx config'",
    f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep -i nginx",
]
for cmd in cmds:
    print(f"\n========= $ {cmd[:120]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("[err]", err.strip()[:200])

c.close()
