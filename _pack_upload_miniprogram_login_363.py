# -*- coding: utf-8 -*-
"""Package miniprogram dir to zip, verify contents, upload via SFTP, verify download URL."""
import os
import sys
import io
import zipfile
import secrets
import datetime
import urllib.request
import urllib.error

import paramiko

LOCAL_DIR = r"C:\auto_output\bnbbaijkgj\miniprogram"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


def make_zip_filename():
    now = datetime.datetime.now()
    hms = now.strftime("%H%M%S")
    h = secrets.token_hex(2)
    return f"miniprogram_login_layout_20260506_{hms}_{h}.zip"


def build_zip(zip_path: str):
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(LOCAL_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if fn in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, LOCAL_DIR)
                arc = rel.replace(os.sep, "/")
                zf.write(full, arc)
                file_count += 1
    return file_count


def verify_zip(zip_path: str):
    required = [
        "app.json",
        "app.js",
        "project.config.json",
        "pages/login/index.wxml",
        "pages/login/index.wxss",
        "pages/login/index.js",
        "pages/login/index.json",
    ]
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        missing = [r for r in required if r not in names]
        if missing:
            raise RuntimeError(f"Missing required files in zip: {missing}")
        wxss = zf.read("pages/login/index.wxss").decode("utf-8", errors="replace")
        js = zf.read("pages/login/index.js").decode("utf-8", errors="replace")
        if "top-brand" not in wxss:
            raise RuntimeError("'top-brand' not found in pages/login/index.wxss")
        if "#2fb56a" not in wxss:
            raise RuntimeError("'#2fb56a' not found in pages/login/index.wxss")
        if "同意并登录" not in js:
            raise RuntimeError("'同意并登录' not found in pages/login/index.js")
    return True


def sftp_upload(zip_path: str, zip_name: str):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    try:
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {REMOTE_DIR}")
        stdout.channel.recv_exit_status()
        sftp = client.open_sftp()
        try:
            remote_path = f"{REMOTE_DIR}/{zip_name}"
            sftp.put(zip_path, remote_path)
            attr = sftp.stat(remote_path)
            print(f"[upload] {remote_path} size={attr.st_size}")
        finally:
            sftp.close()
    finally:
        client.close()


def verify_download(url: str):
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.getcode()
            length = resp.headers.get("Content-Length")
            print(f"[download] HEAD {url} -> {code} length={length}")
            return code == 200
    except urllib.error.HTTPError as e:
        print(f"[download] HTTPError {e.code} for {url}")
        return False


def main():
    if not os.path.isdir(LOCAL_DIR):
        print(f"ERROR: local dir does not exist: {LOCAL_DIR}")
        sys.exit(2)

    zip_name = make_zip_filename()
    zip_path = os.path.join(r"C:\auto_output\bnbbaijkgj", zip_name)
    print(f"[zip] building {zip_path}")
    n = build_zip(zip_path)
    size = os.path.getsize(zip_path)
    print(f"[zip] files={n} size={size}")

    print("[verify] checking zip contents...")
    verify_zip(zip_path)
    print("[verify] OK")

    print("[sftp] uploading...")
    sftp_upload(zip_path, zip_name)

    url = f"{BASE_URL}/miniprogram/{zip_name}"
    print(f"[verify] download url: {url}")
    ok = verify_download(url)
    if not ok:
        print("ERROR: download HEAD did not return 200")
        sys.exit(3)

    print("=" * 60)
    print(f"ZIP_FILENAME={zip_name}")
    print(f"ZIP_DOWNLOAD_URL={url}")


if __name__ == "__main__":
    main()
