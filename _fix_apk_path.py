#!/usr/bin/env python3
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
APK_NAME = "bini_health_coupon_20260504_114911_54f0.apk"
DEPLOY="6b099ed3-7175-4a78-91f4-44570c84ed27"
TARGET_DIR=f"/home/ubuntu/{DEPLOY}/static/apk"
TARGET=f"{TARGET_DIR}/{APK_NAME}"
SRC=f"/data/static/apk/{APK_NAME}"

client=paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=60)
cmd = (
    f"echo '== existing apk dir contents =='\n"
    f"ls -la /home/ubuntu/{DEPLOY}/static/ 2>/dev/null\n"
    f"ls -la {TARGET_DIR} 2>/dev/null | head -20\n"
    f"echo '== copy =='\n"
    f"echo '{PASS}' | sudo -S mkdir -p {TARGET_DIR} && "
    f"echo '{PASS}' | sudo -S cp {SRC} {TARGET} && "
    f"echo '{PASS}' | sudo -S chmod 644 {TARGET} && "
    f"ls -la {TARGET}\n"
)
stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
rc = stdout.channel.recv_exit_status()
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err.strip(): print("STDERR:", err)
print(f"exit={rc}")
client.close()
