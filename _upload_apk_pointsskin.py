"""Upload APK to remote server via SFTP and verify via HTTPS HEAD."""
import os
import sys
import time
import secrets
import urllib.request
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

LOCAL_APK = r"C:\auto_output\bnbbaijkgj\apk_pointsskin_dl\bini_health_android-pointsskin-v20260514-180027-f06b.apk"
TS = time.strftime("%Y%m%d_%H%M%S")
RAND = secrets.token_hex(2)
REMOTE_NAME = f"app_pointsskin_{TS}_{RAND}.apk"
REMOTE_PATH = f"{REMOTE_DIR}/{REMOTE_NAME}"

size = os.path.getsize(LOCAL_APK)
print(f"Local APK: {LOCAL_APK}")
print(f"Size: {size} bytes ({size/1024/1024:.2f} MB)")
print(f"Remote name: {REMOTE_NAME}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
stdout.channel.recv_exit_status()

sftp = ssh.open_sftp()
print("Uploading via SFTP...")
t0 = time.time()
sftp.put(LOCAL_APK, REMOTE_PATH)
dt = time.time() - t0
print(f"Upload done in {dt:.1f}s ({size/1024/1024/dt:.2f} MB/s)")

stat = sftp.stat(REMOTE_PATH)
print(f"Remote size: {stat.st_size}")
assert stat.st_size == size, "Size mismatch!"

sftp.close()

ssh.exec_command(f"chmod 644 {REMOTE_PATH}")[1].channel.recv_exit_status()
ssh.close()

url = f"{BASE_URL}/{REMOTE_NAME}"
print(f"Download URL: {url}")

last_status = None
for attempt in range(5):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            last_status = resp.status
            print(f"HEAD attempt {attempt+1}: HTTP {resp.status}, Content-Length={resp.headers.get('Content-Length')}")
            if resp.status == 200:
                break
    except Exception as e:
        print(f"HEAD attempt {attempt+1} failed: {e}")
        last_status = -1
    time.sleep(5)

print("\n===RESULT===")
print(f"REMOTE_NAME={REMOTE_NAME}")
print(f"URL={url}")
print(f"HTTP_STATUS={last_status}")
print(f"SIZE={size}")
