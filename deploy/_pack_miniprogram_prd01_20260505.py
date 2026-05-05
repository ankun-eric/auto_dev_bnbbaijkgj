# -*- coding: utf-8 -*-
"""
PRD-01 时段切片：打包 miniprogram 目录并上传到测试服务器静态目录。
"""
import os
import sys
import time
import secrets
import zipfile
import subprocess
import paramiko

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
MINIPROGRAM_DIR = os.path.join(PROJECT_ROOT, "miniprogram")

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram"
URL_BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram"

EXCLUDE_DIR_NAMES = {"node_modules", ".git", ".idea", ".vscode", "__pycache__", "miniprogram_npm"}
EXCLUDE_SUFFIXES = (".lock", ".log", ".DS_Store")


def build_zip_name():
    ts = time.strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    return f"miniprogram_prd01_timeslot_{ts}_{rand}.zip"


def should_skip(path_rel):
    parts = path_rel.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIR_NAMES:
            return True
    if path_rel.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def make_zip(zip_path):
    if not os.path.isdir(MINIPROGRAM_DIR):
        raise RuntimeError(f"miniprogram dir missing: {MINIPROGRAM_DIR}")
    if not os.path.isfile(os.path.join(MINIPROGRAM_DIR, "app.json")):
        raise RuntimeError("miniprogram/app.json missing - cannot import to wechat devtools")
    if not os.path.isfile(os.path.join(MINIPROGRAM_DIR, "utils", "timeSlots.js")):
        raise RuntimeError("miniprogram/utils/timeSlots.js missing")

    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MINIPROGRAM_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]
            for fn in files:
                full = os.path.join(root, fn)
                rel_in_mp = os.path.relpath(full, MINIPROGRAM_DIR)
                if should_skip(rel_in_mp):
                    continue
                arcname = os.path.join("miniprogram", rel_in_mp).replace("\\", "/")
                zf.write(full, arcname)
                count += 1
    print(f"[zip] wrote {count} files -> {zip_path} ({os.path.getsize(zip_path)} bytes)")


def sftp_upload(local_path, remote_path):
    transport = paramiko.Transport((SSH_HOST, SSH_PORT))
    transport.connect(username=SSH_USER, password=SSH_PASS)
    try:
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.stat(REMOTE_DIR)
        except IOError:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS)
            ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
            ssh.close()
        sftp.put(local_path, remote_path)
        st = sftp.stat(remote_path)
        print(f"[sftp] uploaded -> {remote_path} ({st.st_size} bytes)")
        sftp.close()
    finally:
        transport.close()


def verify_url(url):
    cp = subprocess.run(
        ["curl", "-k", "-s", "-o", "NUL", "-w", "%{http_code}", "-I", url],
        capture_output=True, text=True, timeout=30,
    )
    code = (cp.stdout or "").strip()
    print(f"[verify] HEAD {url} -> {code}")
    return code


def main():
    zip_name = build_zip_name()
    local_zip = os.path.join(PROJECT_ROOT, "deploy", zip_name)
    remote_zip = f"{REMOTE_DIR}/{zip_name}"
    download_url = f"{URL_BASE}/{zip_name}"

    make_zip(local_zip)
    sftp_upload(local_zip, remote_zip)
    code = verify_url(download_url)

    if code != "200":
        # try GET as a fallback in case HEAD is blocked
        cp = subprocess.run(
            ["curl", "-k", "-s", "-o", "NUL", "-w", "%{http_code}", download_url],
            capture_output=True, text=True, timeout=60,
        )
        code = (cp.stdout or "").strip()
        print(f"[verify-get] GET {download_url} -> {code}")

    print("=" * 60)
    print(f"ZIP_NAME={zip_name}")
    print(f"DOWNLOAD_URL={download_url}")
    print(f"HTTP_STATUS={code}")
    print("=" * 60)
    if code != "200":
        sys.exit(2)


if __name__ == "__main__":
    main()
