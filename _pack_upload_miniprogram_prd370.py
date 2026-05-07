# -*- coding: utf-8 -*-
"""[PRD-370] 打包小程序 zip + 上传 + HEAD 验证。"""
import os
import sys
import zipfile
import secrets
import datetime
import urllib.request
import urllib.error
import ssl

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

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def make_zip_filename():
    now = datetime.datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    h = secrets.token_hex(2)
    return f"miniprogram_prd370_{ts}_{h}.zip"


def build_zip(zip_path: str):
    n = 0
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
                n += 1
    return n


def verify_zip(zip_path: str):
    """验证 PRD-370 关键 token 是否在 zip 中。"""
    required = [
        "app.json", "app.js", "project.config.json",
        "pages/login/index.wxml",
        "pages/login/index.wxss",
        "pages/login/index.js",
    ]
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        for r in required:
            if r not in names:
                raise RuntimeError(f"Missing in zip: {r}")
        wxss = zf.read("pages/login/index.wxss").decode("utf-8", errors="replace")
        wxml = zf.read("pages/login/index.wxml").decode("utf-8", errors="replace")
        js = zf.read("pages/login/index.js").decode("utf-8", errors="replace")
        for token, where, content in [
            ("#34C759", "wxss", wxss),
            ("#4AD97A", "wxss", wxss),
            ("#2BD4C4", "wxss", wxss),
            ("login-page-v370", "wxss", wxss),
            ("agreement-dialog", "wxml", wxml),
            ("agreementDialogVisible", "js", js),
            ("\u670d\u52a1\u534f\u8bae\u53ca\u9690\u79c1\u4fdd\u62a4", "wxml", wxml),  # 服务协议及隐私保护
        ]:
            if token not in content:
                raise RuntimeError(f"Token '{token}' not found in {where}")
    return True


def sftp_upload(zip_path: str, zip_name: str):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    try:
        i, o, e = client.exec_command(f"mkdir -p {REMOTE_DIR}")
        o.channel.recv_exit_status()
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
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            code = resp.getcode()
            length = resp.headers.get("Content-Length")
            print(f"[download] HEAD {url} -> {code} length={length}")
            return code == 200
    except urllib.error.HTTPError as e:
        print(f"[download] HTTPError {e.code} for {url}")
        return False


def main():
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
    print(f"ZIP_SIZE={size}")
    print(f"ZIP_FILECOUNT={n}")


if __name__ == "__main__":
    main()
