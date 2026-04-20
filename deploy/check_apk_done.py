"""轮询服务器 APK 构建状态。"""
import paramiko
import sys

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=60)


def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=60)
    return o.read().decode()


print("=== build script status ===")
print(run('pgrep -af build_apk_v7.sh || echo "build script not running"'))

print("=== flutter container ===")
print(run('docker ps --format "{{.Names}} {{.Status}}" | grep -i flutter || echo "no flutter container"'))

print("=== build log tail ===")
print(run('tail -25 /tmp/flutter_build.log 2>/dev/null'))

print("=== APK files ===")
print(run('ls -lh /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/ 2>/dev/null'))

print("=== nohup tail ===")
print(run('tail -30 /tmp/flutter_build.nohup 2>/dev/null'))

print("=== build dir ===")
print(run('ls -lh /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/flutter_app/build/app/outputs/flutter-apk/ 2>/dev/null'))

c.close()
