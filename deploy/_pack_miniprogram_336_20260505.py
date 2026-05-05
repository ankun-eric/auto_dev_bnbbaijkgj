"""Pack miniprogram/ to zip, upload to deploy server, verify HTTP access.

Subagent task: ship the miniprogram source after the bug-fix
(reschedule button text unification) so users can download via URL.
"""

import os
import random
import ssl
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime

import paramiko

PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"
MINIPROGRAM_DIR = os.path.join(PROJECT_DIR, "miniprogram")

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode", "miniprogram_npm"}
EXCLUDE_EXTS = {".pyc", ".pyo"}

SERVER = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_UUID}/static/miniprogram"
BASE_URL = f"https://{SERVER}/autodev/{PROJECT_UUID}/miniprogram"

RETRY_DELAYS = [10, 20, 40]


def build_zip_name():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_hex = "%04x" % random.randint(0, 0xFFFF)
    return f"miniprogram_{ts}_{rand_hex}.zip"


def make_zip(src_dir, zip_path):
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if os.path.splitext(f)[1] in EXCLUDE_EXTS:
                    continue
                full = os.path.join(root, f)
                arc = os.path.relpath(full, src_dir)
                zf.write(full, arc)
                file_count += 1
    return file_count, os.path.getsize(zip_path)


def with_retry(label, fn):
    last_err = None
    for attempt in range(3):
        try:
            return fn()
        except Exception as e:
            last_err = e
            print(f"    [{label}] attempt {attempt + 1} failed: {e}", file=sys.stderr)
            if attempt < 2:
                delay = RETRY_DELAYS[attempt]
                print(f"    [{label}] retrying in {delay}s...", file=sys.stderr)
                time.sleep(delay)
    raise last_err


def upload(zip_path, remote_path, remote_dir):
    def _do():
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SERVER, username=SSH_USER, password=SSH_PASS, timeout=30)
        try:
            ssh.exec_command(f"mkdir -p {remote_dir}")[1].channel.recv_exit_status()
            sftp = ssh.open_sftp()
            try:
                sftp.put(zip_path, remote_path)
                rstat = sftp.stat(remote_path)
                return rstat.st_size
            finally:
                sftp.close()
        finally:
            ssh.close()
    return with_retry("upload", _do)


def http_check(url):
    cmd = ["curl", "-sk", "-o", "NUL" if os.name == "nt" else "/dev/null",
           "-w", "%{http_code}", url]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return res.stdout.strip(), res.stderr


def http_check_urllib(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, method="HEAD")
    resp = urllib.request.urlopen(req, context=ctx, timeout=20)
    return str(resp.status), resp.headers.get("Content-Length", "?")


def main():
    if not os.path.isdir(MINIPROGRAM_DIR):
        print(f"ERROR: miniprogram dir missing: {MINIPROGRAM_DIR}", file=sys.stderr)
        sys.exit(2)

    zip_name = build_zip_name()
    zip_path = os.path.join(PROJECT_DIR, zip_name)
    remote_path = f"{REMOTE_DIR}/{zip_name}"
    download_url = f"{BASE_URL}/{zip_name}"

    print(f"[1/4] Packing -> {zip_name}")
    n, sz = make_zip(MINIPROGRAM_DIR, zip_path)
    print(f"      {n} files, {sz:,} bytes")

    print(f"[2/4] Uploading to {SERVER}:{remote_path}")
    rsize = upload(zip_path, remote_path, REMOTE_DIR)
    print(f"      remote size: {rsize:,} bytes  ({'OK' if rsize == sz else 'MISMATCH'})")

    print(f"[3/4] HTTP check: {download_url}")
    code, err = http_check(download_url)
    print(f"      curl -> {code!r}")
    if code != "200":
        try:
            ucode, clen = http_check_urllib(download_url)
            print(f"      urllib -> {ucode}  Content-Length={clen}")
            code = ucode
        except Exception as e:
            print(f"      urllib failed: {e}", file=sys.stderr)

    print("[4/4] Cleanup local zip")
    try:
        os.remove(zip_path)
    except Exception as e:
        print(f"      cleanup warning: {e}", file=sys.stderr)

    print()
    print(f"DOWNLOAD_URL={download_url}")
    print(f"HTTP_CODE={code}")
    print(f"ZIP_FILENAME={zip_name}")

    if code != "200":
        sys.exit(1)


if __name__ == "__main__":
    main()
