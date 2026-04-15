import paramiko
import os
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_LOCAL = r"C:\auto_output\bnbbaijkgj\_deploy_tmp\apk_download\app_20260415_003629_8c83.apk"
APK_NAME = "app_20260415_003629_8c83.apk"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

# Check gateway static volume mount
out, err = run("docker inspect gateway --format '{{json .Mounts}}' 2>/dev/null")
print(f"Gateway mounts: {out[:500]}")

# Check if /data/static exists in gateway
out, err = run("docker exec gateway ls -la /data/static/ 2>/dev/null || echo 'NO /data/static'")
print(f"Gateway /data/static: {out}")

# The static files are served from gateway's /data/static/, let's check docker-compose for volume mount
out, err = run(f"cat /home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml | grep -A5 -B5 static")
print(f"Docker compose static config:\n{out}")

ssh.close()
