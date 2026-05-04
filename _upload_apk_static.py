#!/usr/bin/env python3
"""Upload APK to /data/static/apk/ which matches actual nginx alias."""
import os, sys, paramiko

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_NAME="bini_health_coupon_mall_20260504_130854_91a5.apk"
LOCAL=rf"C:\auto_output\bnbbaijkgj\apk_download\{APK_NAME}"
TMP=f"/tmp/{APK_NAME}"
DEST=f"/data/static/apk/{APK_NAME}"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=60,banner_timeout=60)
sftp=c.open_sftp()
print(f"[1/3] put -> {TMP}")
sftp.put(LOCAL, TMP)
print(f"      ok {sftp.stat(TMP).st_size} bytes")
sftp.close()

cmd=(
    f"echo '{PASS}' | sudo -S mkdir -p /data/static/apk && "
    f"echo '{PASS}' | sudo -S mv {TMP} {DEST} && "
    f"echo '{PASS}' | sudo -S chmod 644 {DEST} && "
    f"echo '{PASS}' | sudo -S chown root:root {DEST} && "
    f"ls -la {DEST}"
)
print(f"[2/3] mv -> {DEST}")
_,o,e=c.exec_command(cmd, timeout=120); rc=o.channel.recv_exit_status()
print(o.read().decode("utf-8","replace"))
er=e.read().decode("utf-8","replace")
if er.strip(): print("ERR:",er[:300])
print(f"exit={rc}")

print(f"[3/3] HTTP verify (server-side)")
url=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/apk/{APK_NAME}"
_,o,_=c.exec_command(f"curl -sI -o /dev/null -w 'http=%{{http_code}} clen=%{{size_header}}\\n' '{url}' && curl -sI '{url}' | head -10", timeout=60)
print(o.read().decode())
c.close()
sys.exit(0 if rc==0 else 1)
