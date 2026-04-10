#!/usr/bin/env python3
"""Zip miniprogram (exclude junk), SFTP to server, copy into backend uploads, verify HTTP."""
import os
import random
import sys
import zipfile
from datetime import datetime

import paramiko
import urllib.request

SRC = r"C:\auto_output\bnbbaijkgj\miniprogram"
OUT_DIR = r"C:\auto_output\bnbbaijkgj"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PROJECT_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_BASE = f"/home/ubuntu/{PROJECT_ID}"
BACKEND_CONTAINER = f"{PROJECT_ID}-backend"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"

EXCLUDE_NAMES = {
    "node_modules",
    ".git",
    "__pycache__",
    ".DS_Store",
    "dist",
    "build",
    ".idea",
    ".vscode",
}


def should_skip(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return any(p in EXCLUDE_NAMES for p in parts)


def make_zip_name() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    h = "".join(random.choice("0123456789abcdef") for _ in range(4))
    return f"miniprogram_{ts}_{h}.zip"


def build_zip(dest_path: str, zip_name: str) -> str:
    zpath = os.path.join(dest_path, zip_name)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
            rel_root = os.path.relpath(root, os.path.dirname(SRC))
            if rel_root == ".":
                arc_prefix = "miniprogram"
            else:
                arc_prefix = os.path.join("miniprogram", rel_root)
            for name in files:
                fp = os.path.join(root, name)
                if should_skip(fp):
                    continue
                arc = os.path.join(arc_prefix, name).replace("\\", "/")
                zf.write(fp, arc)
    return zpath


def ssh_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=60)
    return c


def main():
    zip_name = make_zip_name()
    print("Creating:", zip_name)
    zpath = build_zip(OUT_DIR, zip_name)
    size = os.path.getsize(zpath)
    print("Local zip bytes:", size)

    remote_path = f"{REMOTE_BASE}/{zip_name}"
    download_url = f"{BASE_URL}/uploads/{zip_name}"

    client = ssh_client()
    try:
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {REMOTE_BASE}")
        stdout.channel.recv_exit_status()

        sftp = client.open_sftp()
        print("Uploading to", remote_path)
        sftp.put(zpath, remote_path)
        sftp.chmod(remote_path, 0o644)
        sftp.close()

        cmd = (
            f"docker cp {remote_path} {BACKEND_CONTAINER}:/app/uploads/{zip_name} "
            f"&& docker exec {BACKEND_CONTAINER} ls -la /app/uploads/{zip_name}"
        )
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        print("docker cp:", out or err)
        if stdout.channel.recv_exit_status() != 0:
            print("VERIFY_FAIL: docker cp failed")
            return 1
    finally:
        client.close()

    print("HEAD", download_url)
    req = urllib.request.Request(download_url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = r.status
            cl = r.headers.get("Content-Length")
            print("HTTP", code, "Content-Length:", cl)
            if code != 200 or (cl and int(cl) != size):
                return 1
    except Exception as e:
        print("VERIFY_FAIL:", e)
        return 1

    print("DOWNLOAD_URL:", download_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
