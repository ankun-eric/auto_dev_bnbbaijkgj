"""Pack miniprogram/ and upload to deployment server static dir."""
from __future__ import annotations

import datetime as dt
import os
import secrets
import sys
import zipfile
from pathlib import Path

import paramiko
import urllib.request
import urllib.error

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MP_DIR = PROJECT_ROOT / "miniprogram"

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_UUID}/static/miniprogram"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_UUID}/miniprogram"

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".DS_Store", "miniprogram_npm"}
EXCLUDE_SUFFIXES = {".pyc"}


def make_zip_name() -> str:
    now = dt.datetime.now()
    rnd = secrets.token_hex(2)
    return f"miniprogram_promptcfg_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{rnd}.zip"


def build_zip(zip_path: Path) -> int:
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in files:
                if any(name.endswith(suf) for suf in EXCLUDE_SUFFIXES):
                    continue
                fp = Path(root) / name
                rel = fp.relative_to(MP_DIR.parent)
                zf.write(fp, arcname=str(rel).replace("\\", "/"))
                file_count += 1
    return file_count


def upload(local: Path, remote_name: str) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {REMOTE_DIR}")
        stdout.channel.recv_exit_status()
        sftp = client.open_sftp()
        try:
            remote_path = f"{REMOTE_DIR}/{remote_name}"
            sftp.put(str(local), remote_path)
            sftp.chmod(remote_path, 0o644)
        finally:
            sftp.close()
    finally:
        client.close()


def verify(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def main() -> int:
    if not MP_DIR.is_dir():
        print(f"ERROR: miniprogram dir not found: {MP_DIR}")
        return 2

    zip_name = make_zip_name()
    zip_path = PROJECT_ROOT / "deploy" / zip_name
    print(f"[1/4] Packing -> {zip_path}")
    n = build_zip(zip_path)
    size = zip_path.stat().st_size
    print(f"      files={n}, size={size} bytes")

    print(f"[2/4] Uploading to {HOST}:{REMOTE_DIR}/{zip_name}")
    upload(zip_path, zip_name)

    url = f"{BASE_URL}/{zip_name}"
    print(f"[3/4] Verifying URL: {url}")
    code = verify(url)
    print(f"      HTTP {code}")

    print(f"[4/4] Done")
    print(f"ZIP_NAME={zip_name}")
    print(f"HTTP_STATUS={code}")
    print(f"DOWNLOAD_URL={url}")
    return 0 if code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
