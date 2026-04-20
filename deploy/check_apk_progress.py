import paramiko
import sys

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)
cmds = [
    # 显示构建日志
    "tail -120 /tmp/flutter_build_v7_sync2.log 2>/dev/null",
    "echo '=== DOCKER ==='",
    "docker ps --format 'table {{.Names}}\\t{{.Status}}' | head -10",
    "echo '=== APK BUILD DIR ==='",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/flutter_app/build/app/outputs/flutter-apk/ 2>&1",
    "echo '=== STATIC ==='",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/ 2>&1",
]
_, o, _ = c.exec_command("; ".join(cmds), timeout=60)
print(o.read().decode())
c.close()
