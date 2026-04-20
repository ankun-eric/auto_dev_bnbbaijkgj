"""本地下载 APK，然后 SFTP 上传到服务器"""
import urllib.request, os, sys, paramiko, time
TAG = "android-bugfix7-v20260420-112604-05cd"
URL = f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/{TAG}/bini_health_{TAG}.apk"
LOCAL = f"deploy/_apk_{TAG}.apk"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_DIR = f"{PROJ}/static/apk"

if not os.path.exists(LOCAL) or os.path.getsize(LOCAL) < 1024*1024:
    print(f"[*] downloading {URL}")
    t = time.time()
    req = urllib.request.Request(URL, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(LOCAL, "wb") as f:
        size = 0
        while True:
            chunk = r.read(1<<20)
            if not chunk:
                break
            f.write(chunk)
            size += len(chunk)
            print(f"  ... {size/1024/1024:.1f} MB ({(size/1024/1024)/(time.time()-t+0.1):.2f} MB/s)")
    print(f"[*] downloaded {os.path.getsize(LOCAL)} bytes in {time.time()-t:.1f}s")
else:
    print(f"[*] cached: {LOCAL} {os.path.getsize(LOCAL)} bytes")

print("[*] killing previous downloads on server ...")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)
c.exec_command("pkill -9 -f 'dl_apk.sh' 2>/dev/null; pkill -9 -f 'curl.*bini_health' 2>/dev/null; true")
time.sleep(2)

print("[*] uploading ...")
sftp = c.open_sftp()
sftp.put(LOCAL, "/tmp/bini_health_new.apk")
sftp.close()
print(f"[*] published apk via sudo ...")
remote_name = f"bini_health_bugfix7_{TAG}.apk"
cmd = (
    f"echo Newbang888 | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/{remote_name} && "
    f"echo Newbang888 | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/bini_health.apk && "
    f"echo Newbang888 | sudo -S chmod 644 {APK_DIR}/{remote_name} {APK_DIR}/bini_health.apk && "
    f"echo Newbang888 | sudo -S chown ubuntu:ubuntu {APK_DIR}/{remote_name} {APK_DIR}/bini_health.apk && "
    f"ls -la {APK_DIR}/"
)
_, o, e = c.exec_command(cmd, timeout=120)
print(o.read().decode(errors="replace"))
print("ERR:", e.read().decode(errors="replace"))
c.close()
print("[*] done")
print(f"REMOTE_FILE={remote_name}")
