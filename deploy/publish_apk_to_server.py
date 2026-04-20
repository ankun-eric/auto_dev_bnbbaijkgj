"""下载 GH Release APK 到服务器 static/apk/"""
import paramiko, time, sys
TAG = "android-bugfix7-v20260420-112604-05cd"
URL = f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/{TAG}/bini_health_{TAG}.apk"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_DIR = f"{PROJ}/static/apk"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)

script = f"""#!/bin/bash
set -e
cd /tmp
rm -f /tmp/bini_health_new.apk /tmp/apk_dl.ok /tmp/apk_dl.fail
curl -fL --retry 3 -o /tmp/bini_health_new.apk '{URL}' >> /tmp/apk_dl.log 2>&1
echo Newbang888 | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/bini_health_bugfix7_{TAG}.apk
echo Newbang888 | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/bini_health.apk
echo Newbang888 | sudo -S chmod 644 {APK_DIR}/bini_health.apk {APK_DIR}/bini_health_bugfix7_{TAG}.apk
ls -la {APK_DIR}/ >> /tmp/apk_dl.log 2>&1
touch /tmp/apk_dl.ok
"""
print("[*] 上传脚本 ...")
sftp = c.open_sftp()
with sftp.open("/tmp/dl_apk.sh", "w") as f:
    f.write(script)
sftp.chmod("/tmp/dl_apk.sh", 0o755)
sftp.close()

print("[*] 启动后台下载 ...")
c.exec_command("rm -f /tmp/apk_dl.log /tmp/apk_dl.ok /tmp/apk_dl.fail; nohup /tmp/dl_apk.sh > /tmp/apk_dl.run.log 2>&1 &")
time.sleep(2)

for i in range(60):  # 最多 5 分钟
    _, o, _ = c.exec_command("[ -f /tmp/apk_dl.ok ] && echo OK || ([ -f /tmp/apk_dl.fail ] && echo FAIL || echo RUN)")
    s = o.read().decode().strip()
    print(f"[{i*5}s] {s}")
    if s == "OK":
        _, o, _ = c.exec_command("tail -20 /tmp/apk_dl.log")
        print(o.read().decode(errors="replace"))
        c.close()
        sys.exit(0)
    if s == "FAIL":
        _, o, _ = c.exec_command("tail -50 /tmp/apk_dl.log")
        print(o.read().decode(errors="replace"))
        c.close()
        sys.exit(1)
    time.sleep(5)
print("[!] 超时")
c.close()
sys.exit(2)
