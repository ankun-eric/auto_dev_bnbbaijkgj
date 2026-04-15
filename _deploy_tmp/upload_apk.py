import paramiko
import sys
import os

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_LOCAL = r"C:\auto_output\bnbbaijkgj\_deploy_tmp\apk_download\app_20260415_003629_8c83.apk"
APK_NAME = "app_20260415_003629_8c83.apk"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("Connected!")

    # Find where the project is deployed - check docker and nginx configs
    commands_to_check = [
        f"docker ps --filter 'name={DEPLOY_ID}' --format '{{{{.Names}}}} {{{{.Ports}}}}'",
        f"docker ps --format '{{{{.Names}}}}' | grep -i auto",
        f"ls -la /home/ubuntu/projects/{DEPLOY_ID}/ 2>/dev/null || echo 'no projects dir'",
        f"ls -la /var/www/ 2>/dev/null || echo 'no /var/www'",
        f"find /home/ubuntu -maxdepth 3 -name 'docker-compose*' -path '*{DEPLOY_ID[:8]}*' 2>/dev/null || echo 'no compose'",
        f"docker inspect $(docker ps -q --filter 'name={DEPLOY_ID[:8]}') 2>/dev/null | grep -A5 Binds || echo 'no container found by short id'",
        f"docker ps --format '{{{{.Names}}}}' | head -20",
    ]

    for cmd in commands_to_check:
        print(f"\n--- CMD: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(f"OUT: {out}")
        if err:
            print(f"ERR: {err}")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    ssh.close()
