#!/usr/bin/env python3
"""Pack miniprogram/ to zip (with miniprogram/ root prefix) and upload via SFTP.

Verified URL pattern (per existing zips on server):
    https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/miniprogram/{filename}.zip
    -> /home/ubuntu/{DEPLOY_ID}/static/miniprogram/{filename}.zip
"""
import datetime as _dt
import os
import secrets
import sys
import time
import zipfile

import paramiko
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "miniprogram")

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PORT = 22

REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}/miniprogram"

ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
rand = secrets.token_hex(2)
ZIP_NAME = f"miniprogram_{ts}_{rand}.zip"
LOCAL_ZIP = os.path.join(ROOT, ZIP_NAME)
STAGING_REMOTE = f"/home/ubuntu/{ZIP_NAME}"
REMOTE_ZIP = f"{REMOTE_DIR}/{ZIP_NAME}"
DOWNLOAD_URL = f"{BASE_URL}/{ZIP_NAME}"

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", "__MACOSX", ".DS_Store", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDE_EXT = {".log"}


def should_skip(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIRS:
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
    if not os.path.isfile(os.path.join(SRC_DIR, "app.json")):
        print("ERR: miniprogram/app.json not found")
        sys.exit(2)
    if os.path.exists(LOCAL_ZIP):
        os.remove(LOCAL_ZIP)
    count = 0
    total_bytes = 0
    with zipfile.ZipFile(LOCAL_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(SRC_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, SRC_DIR)
                if should_skip(rel):
                    continue
                arcname = "miniprogram/" + rel.replace("\\", "/")
                try:
                    sz = os.path.getsize(full)
                except OSError:
                    continue
                zf.write(full, arcname)
                count += 1
                total_bytes += sz
    zsize = os.path.getsize(LOCAL_ZIP)
    print(f"[zip] {LOCAL_ZIP}")
    print(f"[zip] files={count} src_bytes={total_bytes} zip_bytes={zsize}")
    return zsize


def with_retry(fn, label, attempts=3):
    delays = [5, 15, 30]
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            print(f"[retry] {label} attempt {i + 1} failed: {e}")
            if i < attempts - 1:
                time.sleep(delays[min(i, len(delays) - 1)])
    raise last


def _ssh_run(cmd, timeout=120):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=30)
    try:
        _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
    finally:
        ssh.close()
    return rc, out, err


def upload():
    def _do_upload():
        t = paramiko.Transport((HOST, PORT))
        t.banner_timeout = 30
        t.connect(username=USER, password=PASS)
        sftp = paramiko.SFTPClient.from_transport(t)
        try:
            sftp.put(LOCAL_ZIP, STAGING_REMOTE)
            st = sftp.stat(STAGING_REMOTE)
            print(f"[sftp] staged -> {STAGING_REMOTE} size={st.st_size}")
        finally:
            sftp.close()
            t.close()

    with_retry(_do_upload, "sftp upload to staging")

    def _do_move():
        cmd = (
            f"mkdir -p {REMOTE_DIR} && "
            f"mv -f {STAGING_REMOTE} {REMOTE_ZIP} && "
            f"chmod 644 {REMOTE_ZIP} && "
            f"ls -la {REMOTE_ZIP}"
        )
        rc, out, err = _ssh_run(cmd)
        print(f"[ssh] mv rc={rc}\nSTDOUT: {out}\nSTDERR: {err}")
        if rc != 0:
            raise RuntimeError(f"mv failed rc={rc}: {err}")

    with_retry(_do_move, "ssh move into static dir")


def verify():
    def _do_verify():
        req = urllib.request.Request(DOWNLOAD_URL, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=30)
        size = int(resp.headers.get("Content-Length") or 0)
        ctype = resp.headers.get("Content-Type", "")
        print(f"[verify] HTTP {resp.status} type={ctype} size={size} url={DOWNLOAD_URL}")
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return resp.status, size

    return with_retry(_do_verify, "http verify download", attempts=4)


if __name__ == "__main__":
    zsize = build_zip()
    upload()
    code, served = verify()
    print("---RESULT---")
    print(f"ZIP_NAME={ZIP_NAME}")
    print(f"DOWNLOAD_URL={DOWNLOAD_URL}")
    print(f"HTTP_STATUS={code}")
    print(f"LOCAL_SIZE={zsize}")
    print(f"SERVED_SIZE={served}")
    print("DONE")
