# -*- coding: utf-8 -*-
"""PRD-433 微信小程序打包并上传到部署服务器"""
import os
import sys
import io
import zipfile
import secrets
import datetime
import fnmatch
import urllib.request

import paramiko

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

WORK_DIR = r"C:\auto_output\bnbbaijkgj"
SRC_DIR = os.path.join(WORK_DIR, "miniprogram")

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram"
URL_BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram"

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__"}
EXCLUDE_PATTERNS = ["*.pyc", ".DS_Store"]

REQUIRED_FILES = [
    "app.json",
    "project.config.json",
    "pages/chat/index.wxml",
    "pages/chat/index.wxss",
]


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def should_exclude(name):
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def build_zip(zip_path):
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for root, dirs, files in os.walk(SRC_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if should_exclude(f):
                    continue
                abs_p = os.path.join(root, f)
                rel_p = os.path.relpath(abs_p, SRC_DIR).replace(os.sep, "/")
                zf.write(abs_p, arcname=rel_p)
                file_count += 1
    return file_count


def verify_zip(zip_path):
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    missing = [r for r in REQUIRED_FILES if r not in names]
    return names, missing


def sftp_upload(local_path, remote_path):
    transport = paramiko.Transport((SSH_HOST, SSH_PORT))
    transport.connect(username=SSH_USER, password=SSH_PASS)
    try:
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.stat(REMOTE_DIR)
        except IOError:
            parts = REMOTE_DIR.strip("/").split("/")
            cur = ""
            for p in parts:
                cur += "/" + p
                try:
                    sftp.stat(cur)
                except IOError:
                    sftp.mkdir(cur)
        sftp.put(local_path, remote_path)
        st = sftp.stat(remote_path)
        sftp.close()
        return st.st_size
    finally:
        transport.close()


def ssh_exec(cmd):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    try:
        stdin, stdout, stderr = cli.exec_command(cmd, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err
    finally:
        cli.close()


def head_local(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, dict(resp.headers)
    except Exception as e:
        return None, str(e)


def main():
    if not os.path.isdir(SRC_DIR):
        log(f"错误：源码目录不存在 {SRC_DIR}")
        return 1

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    zip_name = f"miniprogram_prd433_{ts}_{rand}.zip"
    zip_path = os.path.join(WORK_DIR, zip_name)
    log(f"目标 zip 文件名: {zip_name}")

    log("开始打包 miniprogram/ 目录 ...")
    file_count = build_zip(zip_path)
    zip_size = os.path.getsize(zip_path)
    log(f"打包完成: 文件数={file_count}, 大小={zip_size} bytes ({zip_size/1024:.1f} KB)")

    log("校验 zip 内必备文件 ...")
    names, missing = verify_zip(zip_path)
    if missing:
        log(f"错误：缺少必备文件 {missing}")
        return 2
    for r in REQUIRED_FILES:
        log(f"  OK 包含 {r}")
    log(f"zip 内总条目数: {len(names)}")

    remote_path = f"{REMOTE_DIR}/{zip_name}"
    log(f"开始 SFTP 上传到 {remote_path} ...")
    remote_size = sftp_upload(zip_path, remote_path)
    log(f"SFTP 上传完成: 远端大小={remote_size} bytes")
    if remote_size != zip_size:
        log(f"警告：远端大小与本地不一致 (local={zip_size}, remote={remote_size})")

    rc, out, err = ssh_exec(f"ls -la {remote_path}")
    log(f"远端 ls -la: rc={rc}\n{out.strip()}\n{err.strip()}")

    download_url = f"{URL_BASE}/{zip_name}"
    log(f"下载 URL: {download_url}")

    curl_cmd = f"curl -sS -o /dev/null -w '%{{http_code}}|%{{size_download}}|%{{content_type}}' -I '{download_url}'"
    rc, out, err = ssh_exec(curl_cmd)
    log(f"远端 curl HEAD: rc={rc}, out={out!r}, err={err.strip()!r}")
    remote_status = out.split("|")[0].strip() if out else ""
    log(f"远端 HEAD 状态码: {remote_status}")

    log("本地 HEAD 验证 ...")
    local_status, local_info = head_local(download_url)
    if local_status:
        log(f"本地 HEAD 状态码: {local_status}")
        for k in ("Content-Type", "Content-Length", "Last-Modified"):
            if k in local_info:
                log(f"  {k}: {local_info[k]}")
    else:
        log(f"本地 HEAD 失败: {local_info}")

    log("=" * 60)
    log("【最终摘要】")
    log(f"zip 文件名     : {zip_name}")
    log(f"zip 大小       : {zip_size} bytes")
    log(f"zip 文件条目数 : {file_count}")
    log(f"下载 URL       : {download_url}")
    log(f"远端 HEAD 状态 : {remote_status}")
    log(f"本地 HEAD 状态 : {local_status}")
    log("=" * 60)

    ok = (remote_status == "200")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
