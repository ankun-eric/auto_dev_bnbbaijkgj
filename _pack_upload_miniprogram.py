#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot script: zip miniprogram, SFTP upload, verify HTTP 200."""
import os
import sys
import zipfile
import secrets
import subprocess
from datetime import datetime

import paramiko

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
SRC_DIR = os.path.join(PROJECT_ROOT, "miniprogram")
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
HOME_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
URL_PREFIX = f"{BASE_URL}/miniprogram"

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"

EXCLUDE_DIRS = {".git", "__MACOSX", "node_modules"}


def make_zip_name():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    return f"miniprogram_{ts}_{rand}.zip"


def build_zip(zip_path, src_dir):
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, src_dir)
                arcname = os.path.join("miniprogram", rel_path).replace("\\", "/")
                zf.write(abs_path, arcname)
                count += 1
    return count


def sftp_upload(local_path, remote_path):
    transport = paramiko.Transport((HOST, 22))
    transport.connect(username=USER, password=PWD)
    sftp = paramiko.SFTPClient.from_transport(transport)
    try:
        sftp.put(local_path, remote_path)
        st = sftp.stat(remote_path)
        return st.st_size
    finally:
        sftp.close()
        transport.close()


def ssh_exec(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=20)
    try:
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err
    finally:
        client.close()


def curl_check(url):
    try:
        result = subprocess.run(
            ["curl", "-sk", "-o", "NUL" if os.name == "nt" else "/dev/null",
             "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERR:{e}"


def main():
    zip_name = make_zip_name()
    local_zip = os.path.join(PROJECT_ROOT, zip_name)
    remote_zip = f"{REMOTE_ROOT}/{zip_name}"
    home_zip = f"{HOME_ROOT}/{zip_name}"
    download_url = f"{URL_PREFIX}/{zip_name}"

    print(f"[1/5] Zip name: {zip_name}")
    print(f"[2/5] Building zip from: {SRC_DIR}")
    file_count = build_zip(local_zip, SRC_DIR)
    local_size = os.path.getsize(local_zip)
    print(f"      packed {file_count} files, local size={local_size} bytes ({local_size/1024:.2f} KB)")

    print(f"[3/5] SFTP upload -> {home_zip} (staging)")
    remote_size = sftp_upload(local_zip, home_zip)
    print(f"      remote size={remote_size} bytes")

    print(f"      Moving to web root: {remote_zip}")
    rc_mv, out_mv, err_mv = ssh_exec(
        f"cp {home_zip} {remote_zip} && chmod 644 {remote_zip} && ls -la {remote_zip}"
    )
    print(f"      rc={rc_mv}\n      {out_mv.strip()}")
    if err_mv.strip():
        print(f"      stderr: {err_mv.strip()}")

    print(f"[4/5] ssh ls -la {remote_zip}")
    rc, out, err = ssh_exec(f"ls -la {remote_zip}")
    print(f"      rc={rc}")
    print(f"      {out.strip()}")
    if err.strip():
        print(f"      stderr: {err.strip()}")

    print(f"[5/5] curl check: {download_url}")
    code = curl_check(download_url)
    print(f"      HTTP code: {code}")

    success = (rc == 0) and (code == "200") and (remote_size == local_size)
    size_kb = round(local_size / 1024, 2)

    print("\n=========== RESULT ===========")
    print(f"upload_success: {'YES' if success else 'NO'}")
    print(f"download_url:   {download_url}")
    print(f"file_size_kb:   {size_kb}")
    print(f"http_code:      {code}")
    print(f"local_bytes:    {local_size}")
    print(f"remote_bytes:   {remote_size}")
    print("==============================")

    try:
        os.remove(local_zip)
    except Exception:
        pass

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
