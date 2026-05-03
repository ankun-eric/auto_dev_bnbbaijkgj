"""快速检查服务器 APK 与项目部署状态"""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=30)

cmds = [
    f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>&1 | head -30",
    f"find /home/ubuntu/{DEPLOY_ID}/ -maxdepth 4 -name '*.apk' 2>/dev/null",
    f"find /home/ubuntu/{DEPLOY_ID}/ -maxdepth 5 -type d -name 'apk' 2>/dev/null",
    f"find /home/ubuntu/{DEPLOY_ID}/ -maxdepth 5 -type d -name 'static' 2>/dev/null",
    f"ls /home/ubuntu/{DEPLOY_ID}/static/ 2>&1 || echo NO_STATIC_DIR",
    f"ls /home/ubuntu/{DEPLOY_ID}/static/apk/ 2>&1 || echo NO_APK_DIR",
    "docker ps --filter name=" + DEPLOY_ID + " --format '{{.Names}} | {{.Status}}'",
    "cat /etc/nginx/conf.d/gateway.conf 2>/dev/null | grep -i '" + DEPLOY_ID + "' | head -10 || echo NO_NGINX_LINES",
]
for c in cmds:
    print(f"\n>>>>>>>>> {c}")
    _, stdout, stderr = cli.exec_command(c)
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    print(out)
    if err.strip():
        print("ERR:", err)

cli.close()
