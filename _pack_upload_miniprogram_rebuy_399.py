# -*- coding: utf-8 -*-
"""[BUG-FIX-REBUY-V1 2026-05-07] 打包小程序 zip + 上传 + HEAD 验证。"""
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
    return f"miniprogram_rebuy_{ts}_{h}.zip"


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
    """验证 BUG-FIX-REBUY-V1 关键 token 是否在 zip 中。"""
    required = [
        "app.json", "app.js", "project.config.json",
        "pages/unified-orders/index.wxml",
        "pages/unified-orders/index.js",
        "pages/unified-order-detail/index.wxml",
        "pages/unified-order-detail/index.js",
    ]
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        for r in required:
            if r not in names:
                raise RuntimeError(f"Missing in zip: {r}")
        # 列表页 wxml/js
        wxml_list = zf.read("pages/unified-orders/index.wxml").decode("utf-8", errors="replace")
        js_list = zf.read("pages/unified-orders/index.js").decode("utf-8", errors="replace")
        # 详情页 wxml/js
        wxml_detail = zf.read("pages/unified-order-detail/index.wxml").decode("utf-8", errors="replace")
        js_detail = zf.read("pages/unified-order-detail/index.js").decode("utf-8", errors="replace")
        # 必须包含的关键 token
        checks = [
            (u"\u518d\u6765\u4e00\u5355", "wxml_list", wxml_list),  # 再来一单
            ("onRebuy", "js_list", js_list),
            ("/reorder", "js_list", js_list),
            ("from_rebuy", "js_list", js_list),
            (u"\u518d\u6765\u4e00\u5355", "wxml_detail", wxml_detail),  # 再来一单
            ("onRebuy", "js_detail", js_detail),
            ("/reorder", "js_detail", js_detail),
        ]
        for token, where, content in checks:
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
