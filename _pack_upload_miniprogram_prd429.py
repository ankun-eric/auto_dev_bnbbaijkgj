# -*- coding: utf-8 -*-
"""[PRD-429] AI 回答消息满屏排版改造 - 打包小程序 zip + 上传 + HEAD 验证。

本次小程序端改动文件：
- miniprogram/pages/chat/index.wxml （消息列表结构调整为满屏排版）
- miniprogram/pages/chat/index.wxss （新增 .msg-flow-row 等满屏排版样式）
"""
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
EXCLUDE_EXTS = {".log"}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def make_zip_filename():
    now = datetime.datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    h = secrets.token_hex(2)
    return f"miniprogram_prd429_{ts}_{h}.zip"


def build_zip(zip_path: str):
    n = 0
    total_src = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(LOCAL_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if fn in EXCLUDE_FILES:
                    continue
                ext = os.path.splitext(fn)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, LOCAL_DIR)
                arc = rel.replace(os.sep, "/")
                try:
                    total_src += os.path.getsize(full)
                except OSError:
                    pass
                zf.write(full, arc)
                n += 1
    return n, total_src


def verify_zip_basic(zip_path: str):
    required = ["app.json", "app.js", "project.config.json"]
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        critical = ["pages/chat/index.wxml", "pages/chat/index.wxss", "pages/chat/index.js"]
        for r in required + critical:
            if r not in names:
                raise RuntimeError(f"Missing in zip: {r}")
        # 验证本次新增的 .msg-flow-row 满屏排版样式确实存在
        wxss_data = zf.read("pages/chat/index.wxss").decode("utf-8", "replace")
        if ".msg-flow-row" not in wxss_data:
            raise RuntimeError("missing .msg-flow-row in pages/chat/index.wxss")
        wxml_data = zf.read("pages/chat/index.wxml").decode("utf-8", "replace")
        if "msg-flow-header" not in wxml_data:
            raise RuntimeError("missing msg-flow-header in pages/chat/index.wxml")
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
            return remote_path
        finally:
            sftp.close()
    finally:
        client.close()


def ssh_curl_verify(url: str):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    try:
        cmd = f'curl -sL -I -o /dev/null -w "%{{http_code}}" "{url}"'
        i, o, e = client.exec_command(cmd)
        out = o.read().decode("utf-8", errors="replace").strip()
        err = e.read().decode("utf-8", errors="replace").strip()
        print(f"[curl] cmd={cmd}")
        print(f"[curl] http_code={out}")
        if err:
            print(f"[curl] stderr={err}")
        return out
    finally:
        client.close()


def verify_download_local(url: str):
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            code = resp.getcode()
            length = resp.headers.get("Content-Length")
            print(f"[download] HEAD {url} -> {code} length={length}")
            return code
    except urllib.error.HTTPError as e:
        print(f"[download] HTTPError {e.code} for {url}")
        return e.code
    except Exception as ex:
        print(f"[download] error: {ex}")
        return None


def main():
    zip_name = make_zip_filename()
    zip_path = os.path.join(r"C:\auto_output\bnbbaijkgj", zip_name)
    print(f"[zip] building {zip_path}")
    n, src_size = build_zip(zip_path)
    size = os.path.getsize(zip_path)
    print(f"[zip] files={n} src_size={src_size} zip_size={size}")

    print("[verify] checking zip contents (含 PRD-429 满屏排版改动)...")
    verify_zip_basic(zip_path)
    print("[verify] OK (app.json + project.config.json + pages/chat/* + .msg-flow-row 全部存在)")

    print("[sftp] uploading...")
    sftp_upload(zip_path, zip_name)

    url = f"{BASE_URL}/miniprogram/{zip_name}"
    print(f"[verify] download url: {url}")

    code_ssh = ssh_curl_verify(url)
    code_local = verify_download_local(url)

    print("=" * 60)
    print(f"ZIP_FILENAME={zip_name}")
    print(f"ZIP_DOWNLOAD_URL={url}")
    print(f"ZIP_SIZE={size}")
    print(f"ZIP_FILECOUNT={n}")
    print(f"HTTP_CODE_SSH_CURL={code_ssh}")
    print(f"HTTP_CODE_LOCAL_HEAD={code_local}")

    if str(code_ssh) != "200":
        print("ERROR: SSH curl did not return 200")
        sys.exit(3)


if __name__ == "__main__":
    main()
