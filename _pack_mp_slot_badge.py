#!/usr/bin/env python3
"""Pack miniprogram/ to zip with slot-badge-tagged filename and SFTP upload."""
import os
import sys
import time
import secrets
import zipfile
import datetime
import paramiko

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "miniprogram")

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
rand = secrets.token_hex(2)
ZIP_NAME = f"miniprogram_slot_badge_{ts}_{rand}.zip"
LOCAL_ZIP = os.path.join(ROOT, ZIP_NAME)

PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}/static/miniprogram"
REMOTE_ZIP = f"{REMOTE_DIR}/{ZIP_NAME}"
URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/miniprogram/{ZIP_NAME}"

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__"}
EXCLUDE_FILES = {".DS_Store"}
EXCLUDE_EXT = {".log"}


def should_skip(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIRS:
            return True
        if p.startswith("."):
            return True
    base = parts[-1]
    if base in EXCLUDE_FILES:
        return True
    _, ext = os.path.splitext(base)
    if ext.lower() in EXCLUDE_EXT:
        return True
    return False


def build_zip():
    if not os.path.isdir(SRC_DIR):
        print(f"ERR: src dir not found: {SRC_DIR}")
        sys.exit(2)
    if os.path.exists(LOCAL_ZIP):
        os.remove(LOCAL_ZIP)
    count = 0
    total = 0
    with zipfile.ZipFile(LOCAL_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(SRC_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for fn in files:
                if fn.startswith("."):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, SRC_DIR)
                if should_skip(rel):
                    continue
                arcname = rel.replace("\\", "/")
                try:
                    sz = os.path.getsize(full)
                except OSError:
                    continue
                zf.write(full, arcname)
                count += 1
                total += sz
    zsize = os.path.getsize(LOCAL_ZIP)
    print(f"[zip] {LOCAL_ZIP} files={count} src={total} zip={zsize}")
    return zsize


def with_retry(fn, label, attempts=3):
    delays = [5, 10, 20]
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            print(f"[retry] {label} attempt {i+1} failed: {e}")
            if i < attempts - 1:
                time.sleep(delays[i])
    raise last_exc


def ensure_remote_dir():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    try:
        cmd = f"mkdir -p {REMOTE_DIR} && ls -ld {REMOTE_DIR}"
        i, o, e = ssh.exec_command(cmd)
        print("[mkdir]", o.read().decode().strip(), e.read().decode().strip())
    finally:
        ssh.close()


def upload():
    def _do_upload():
        t = paramiko.Transport((HOST, 22))
        t.banner_timeout = 30
        t.connect(username=USER, password=PASS)
        sftp = paramiko.SFTPClient.from_transport(t)
        try:
            sftp.put(LOCAL_ZIP, REMOTE_ZIP)
            st = sftp.stat(REMOTE_ZIP)
            print(f"[sftp] uploaded -> {REMOTE_ZIP} size={st.st_size}")
        finally:
            sftp.close()
            t.close()

    with_retry(_do_upload, "sftp upload")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    try:
        i, o, e = ssh.exec_command(f"chmod 644 {REMOTE_ZIP} && ls -la {REMOTE_ZIP}")
        print("[ssh]", o.read().decode().strip(), e.read().decode().strip())
    finally:
        ssh.close()


def verify():
    import urllib.request
    req = urllib.request.Request(URL, method="HEAD")
    attempts = 0
    for i in range(5):
        attempts = i + 1
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            print(f"[verify] attempt {attempts} HTTP {resp.status} URL={URL}")
            if resp.status == 200:
                return resp.status, attempts
        except Exception as ex:
            print(f"[verify] attempt {attempts} failed: {ex}")
        time.sleep(5)
    return 0, attempts


if __name__ == "__main__":
    zsize = build_zip()
    ensure_remote_dir()
    upload()
    code, tries = verify()
    print("=" * 50)
    print(f"ZIP_NAME: {ZIP_NAME}")
    print(f"LOCAL_ZIP: {LOCAL_ZIP}")
    print(f"LOCAL_SIZE: {zsize}")
    print(f"REMOTE_ZIP: {REMOTE_ZIP}")
    print(f"URL: {URL}")
    print(f"HTTP: {code}")
    print(f"VERIFY_ATTEMPTS: {tries}")
    if code != 200:
        sys.exit(1)
