"""上传 9bugs 版本 APK 到服务器，覆盖最新快捷链接，并验证下载 URL"""
import os, sys, time, random, paramiko, urllib.request

TAG = "android-9bugs-v20260421-004119-935c"
LOCAL = os.path.join(os.path.dirname(__file__), f"bini_health_{TAG}.apk")
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_DIR = f"{PROJ}/static/apk"
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk"

TS = time.strftime("%Y%m%d%H%M%S")
RAND = f"{random.randint(0, 0xffff):04x}"
REMOTE_NAME = f"bini_health_9bugs_{TS}_{RAND}.apk"

assert os.path.exists(LOCAL), f"Local APK missing: {LOCAL}"
size_mb = os.path.getsize(LOCAL) / 1024 / 1024
print(f"[*] local: {LOCAL} ({size_mb:.2f} MB)")

print("[*] connecting to server ...")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)

print("[*] uploading to /tmp/bini_health_new.apk ...")
sftp = c.open_sftp()
t0 = time.time()
sftp.put(LOCAL, "/tmp/bini_health_new.apk")
sftp.close()
print(f"[*] uploaded in {time.time()-t0:.1f}s")

cmd = (
    f"echo Newbang888 | sudo -S mkdir -p {APK_DIR} && "
    f"echo Newbang888 | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/{REMOTE_NAME} && "
    f"echo Newbang888 | sudo -S cp /tmp/bini_health_new.apk {APK_DIR}/bini_health.apk && "
    f"echo Newbang888 | sudo -S chmod 644 {APK_DIR}/{REMOTE_NAME} {APK_DIR}/bini_health.apk && "
    f"echo Newbang888 | sudo -S chown ubuntu:ubuntu {APK_DIR}/{REMOTE_NAME} {APK_DIR}/bini_health.apk && "
    f"ls -la {APK_DIR}/ | tail -20"
)
_, o, e = c.exec_command(cmd, timeout=180)
out = o.read().decode(errors="replace")
err = e.read().decode(errors="replace")
print(out)
if err.strip():
    print("STDERR:", err)
c.close()

URL_VER = f"{BASE_URL}/{REMOTE_NAME}"
URL_LATEST = f"{BASE_URL}/bini_health.apk"

def check(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Length")
    except Exception as ex:
        return None, str(ex)

print("\n[*] verifying URLs ...")
s1, l1 = check(URL_VER)
print(f"  {URL_VER}  -> HTTP {s1}  size={l1}")
s2, l2 = check(URL_LATEST)
print(f"  {URL_LATEST}  -> HTTP {s2}  size={l2}")

print(f"\nTAG={TAG}")
print(f"REMOTE_FILE={REMOTE_NAME}")
print(f"URL_VERSION={URL_VER}")
print(f"URL_LATEST={URL_LATEST}")
print(f"HTTP_VERSION={s1}")
print(f"HTTP_LATEST={s2}")
