import os
import zipfile
import random
import time
import paramiko
import urllib.request
import ssl
from datetime import datetime

PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"
MINIPROGRAM_DIR = os.path.join(PROJECT_DIR, "miniprogram")

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode"}
EXCLUDE_EXTS = {".pyc", ".pyo"}

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
rand_hex = "%04x" % random.randint(0, 0xFFFF)
zip_name = f"miniprogram_{timestamp}_{rand_hex}.zip"
zip_path = os.path.join(PROJECT_DIR, zip_name)

SERVER = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PATH = f"{REMOTE_DIR}/{zip_name}"
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
DOWNLOAD_URL = f"{BASE_URL}/{zip_name}"

print(f"[1/3] Creating zip: {zip_name}")
file_count = 0
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(MINIPROGRAM_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if os.path.splitext(f)[1] in EXCLUDE_EXTS:
                continue
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, MINIPROGRAM_DIR)
            zf.write(full_path, arcname)
            file_count += 1

zip_size = os.path.getsize(zip_path)
print(f"    Zipped {file_count} files, size: {zip_size:,} bytes")

print(f"[2/3] Uploading to {SERVER}:{REMOTE_PATH}")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=SSH_USER, password=SSH_PASS, timeout=30)
sftp = ssh.open_sftp()
sftp.put(zip_path, REMOTE_PATH)

remote_stat = sftp.stat(REMOTE_PATH)
print(f"    Upload complete. Remote size: {remote_stat.st_size:,} bytes")
if remote_stat.st_size != zip_size:
    print("    WARNING: Size mismatch!")
else:
    print("    Size verified OK.")

sftp.close()
ssh.close()

print(f"[3/3] Verifying HTTP access: {DOWNLOAD_URL}")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    req = urllib.request.Request(DOWNLOAD_URL, method="HEAD")
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    print(f"    HTTP {resp.status} - OK")
    content_length = resp.headers.get("Content-Length", "unknown")
    print(f"    Content-Length: {content_length}")
except Exception as e:
    print(f"    HTTP verification failed: {e}")
    print("    The file may still be accessible - check the URL manually.")

os.remove(zip_path)
print(f"\n    Local zip cleaned up.")
print(f"\nDOWNLOAD URL: {DOWNLOAD_URL}")
