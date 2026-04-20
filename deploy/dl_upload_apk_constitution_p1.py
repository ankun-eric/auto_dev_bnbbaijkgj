"""一期体质测评 - 本地下载 GH Release 的 APK 然后 SFTP 上传到服务器 static/apk/"""
import os
import sys
import time
import urllib.request

import paramiko

TAG = "android-constitution-p1-20260420-142003"
URL = f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/{TAG}/bini_health_{TAG}.apk"
LOCAL = f"deploy/_apk_{TAG}.apk"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_DIR = f"{PROJ}/static/apk"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

if not os.path.exists(LOCAL) or os.path.getsize(LOCAL) < 1024 * 1024:
    print(f"[*] downloading {URL}")
    t = time.time()
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(LOCAL, "wb") as f:
        size = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            size += len(chunk)
            if size % (5 << 20) == 0 or len(chunk) < (1 << 20):
                print(f"  ... {size/1024/1024:.1f} MB")
    print(f"[*] downloaded {os.path.getsize(LOCAL)} bytes in {time.time()-t:.1f}s")
else:
    print(f"[*] cached: {LOCAL} {os.path.getsize(LOCAL)} bytes")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=60)

print("[*] uploading via SFTP ...")
sftp = c.open_sftp()
sftp.put(LOCAL, "/tmp/bini_health_new.apk")
sftp.close()

remote_name = f"bini_health_{TAG}.apk"
cmd = (
    f"echo {PASS} | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/{remote_name} && "
    f"echo {PASS} | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/bini_health.apk && "
    f"echo {PASS} | sudo -S chmod 644 {APK_DIR}/{remote_name} {APK_DIR}/bini_health.apk && "
    f"echo {PASS} | sudo -S chown ubuntu:ubuntu {APK_DIR}/{remote_name} {APK_DIR}/bini_health.apk && "
    f"ls -lh {APK_DIR}/ | tail -5"
)
_, o, e = c.exec_command(cmd, timeout=120)
print(o.read().decode(errors="replace"))
err = e.read().decode(errors="replace")
if err.strip():
    print("ERR:", err)
c.close()
print("[*] done")
print(f"APK URL: https://{HOST}/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk")
print(f"APK URL: https://{HOST}/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/{remote_name}")
