"""Package miniprogram/ -> zip, upload to server static/downloads, verify HTTPS link."""
import os
import sys
import zipfile
import random
import ssl
import urllib.request
from datetime import datetime

import paramiko

PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"
MINIPROGRAM_DIR = os.path.join(PROJECT_DIR, "miniprogram")

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store"}
EXCLUDE_EXTS = {".pyc", ".pyo"}

SERVER = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# Host path mounted into gateway container at /data/static
HOST_STATIC_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/downloads"

BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
rhex = "%04x" % random.randint(0, 0xFFFF)
ZIP_NAME = f"miniprogram_{ts}_{rhex}.zip"
LOCAL_ZIP = os.path.join(PROJECT_DIR, ZIP_NAME)
REMOTE_ZIP = f"{HOST_STATIC_DIR}/{ZIP_NAME}"

# Two candidate URLs (gateway has both rules):
# 1) regex catch-all:   /autodev/{ID}/<file>.zip -> alias /data/static/downloads/<file>
# 2) explicit prefix:   /autodev/{ID}/downloads/<file>.zip -> alias /data/static/downloads/
URL_PRIMARY = f"{BASE_URL}/{ZIP_NAME}"
URL_FALLBACK = f"{BASE_URL}/downloads/{ZIP_NAME}"

print(f"[1/4] Creating zip: {ZIP_NAME}")
file_count = 0
with zipfile.ZipFile(LOCAL_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for root, dirs, files in os.walk(MINIPROGRAM_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f in EXCLUDE_FILES:
                continue
            if os.path.splitext(f)[1] in EXCLUDE_EXTS:
                continue
            full = os.path.join(root, f)
            arc = os.path.relpath(full, MINIPROGRAM_DIR)
            zf.write(full, arc)
            file_count += 1
zip_size = os.path.getsize(LOCAL_ZIP)
print(f"      packed {file_count} files, {zip_size:,} bytes")

print(f"[2/4] SSH connect & ensure remote dir: {HOST_STATIC_DIR}")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=SSH_USER, password=SSH_PASS, timeout=30)
i, o, e = ssh.exec_command(f"mkdir -p {HOST_STATIC_DIR} && echo OK")
print("      mkdir:", o.read().decode().strip(), e.read().decode().strip())

print(f"[3/4] SFTP upload -> {REMOTE_ZIP}")
sftp = ssh.open_sftp()
sftp.put(LOCAL_ZIP, REMOTE_ZIP)
remote_size = sftp.stat(REMOTE_ZIP).st_size
sftp.close()
print(f"      remote size: {remote_size:,} bytes  (match={remote_size == zip_size})")

# Sanity: list remote dir
i, o, e = ssh.exec_command(f"ls -la {REMOTE_ZIP}")
print("     ", o.read().decode().strip())
ssh.close()

print(f"[4/4] HTTPS verification")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def head(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as ex:
        return ex.code, {}
    except Exception as ex:
        return None, {"error": str(ex)}

final_url = None
final_code = None
final_headers = {}
for url in (URL_PRIMARY, URL_FALLBACK):
    code, hdr = head(url)
    print(f"      HEAD {url} -> {code}  CL={hdr.get('Content-Length')}")
    if code == 200:
        final_url = url
        final_code = code
        final_headers = hdr
        break

# Cleanup local zip
try:
    os.remove(LOCAL_ZIP)
except OSError:
    pass

print()
print("===================== RESULT =====================")
print(f"FILENAME     : {ZIP_NAME}")
print(f"ZIP_SIZE     : {zip_size:,} bytes")
print(f"REMOTE_PATH  : {REMOTE_ZIP}")
print(f"DOWNLOAD_URL : {final_url or URL_PRIMARY}")
print(f"HTTP_STATUS  : {final_code}")
if final_headers.get("Content-Length"):
    print(f"CONTENT_LEN  : {final_headers.get('Content-Length')}")
print("==================================================")
sys.exit(0 if final_code == 200 else 2)
