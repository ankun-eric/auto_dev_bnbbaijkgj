# -*- coding: utf-8 -*-
"""
PRD-03 客户端改期能力收口 v1.0：打包 miniprogram 目录并上传到测试服务器静态目录。

要求：
- zip 根目录为小程序代码本身（解压后即可见 app.json / project.config.json），
  以便直接用「微信开发者工具」导入。
- 排除 node_modules/、.git/、*.log 等无关内容。
- 上传到 /home/ubuntu/<deployId>/static/miniprogram/，
  通过 {baseUrl}/static/miniprogram/<zip> HTTPS 下载。
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
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
# 任务说明：Nginx 已映射 {baseUrl}/static/miniprogram/* -> /home/ubuntu/<deployId>/static/miniprogram/*。
# 同时保留无 static/ 的兜底路径以兼容历史 PRD-01 部署习惯。
URL_BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/static/miniprogram"
URL_BASE_FALLBACK = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/miniprogram"

EXCLUDE_DIR_NAMES = {"node_modules", ".git", ".idea", ".vscode", "__pycache__", "miniprogram_npm"}
EXCLUDE_SUFFIXES = (".log", ".DS_Store")


def build_zip_name():
    ts = time.strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    return f"miniprogram_{ts}_{rand}.zip"


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
    if not os.path.isfile(os.path.join(MINIPROGRAM_DIR, "project.config.json")):
        raise RuntimeError("miniprogram/project.config.json missing - cannot import to wechat devtools")

    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MINIPROGRAM_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]
            for fn in files:
                full = os.path.join(root, fn)
                rel_in_mp = os.path.relpath(full, MINIPROGRAM_DIR)
                if should_skip(rel_in_mp):
                    continue
                arcname = rel_in_mp.replace("\\", "/")
                zf.write(full, arcname)
                count += 1
    print(f"[zip] wrote {count} files -> {zip_path} ({os.path.getsize(zip_path)} bytes)")


def sftp_upload(local_path, remote_path):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    try:
        stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
        stdout.channel.recv_exit_status()
        sftp = ssh.open_sftp()
        try:
            sftp.put(local_path, remote_path)
            st = sftp.stat(remote_path)
            print(f"[sftp] uploaded -> {remote_path} ({st.st_size} bytes)")
            return st.st_size
        finally:
            sftp.close()
    finally:
        ssh.close()


def verify_url(url):
    curl_bin = "curl.exe" if os.name == "nt" else "curl"
    cp = subprocess.run(
        [curl_bin, "-k", "-s", "-o", os.devnull, "-w", "%{http_code}", "-I", url],
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
    remote_size = sftp_upload(local_zip, remote_zip)
    code = verify_url(download_url)

    if code != "200":
        curl_bin = "curl.exe" if os.name == "nt" else "curl"
        cp = subprocess.run(
            [curl_bin, "-k", "-s", "-o", os.devnull, "-w", "%{http_code}", download_url],
            capture_output=True, text=True, timeout=60,
        )
        code = (cp.stdout or "").strip()
        print(f"[verify-get] GET {download_url} -> {code}")

    final_url = download_url
    if code != "200":
        fallback_url = f"{URL_BASE_FALLBACK}/{zip_name}"
        fb_code = verify_url(fallback_url)
        if fb_code != "200":
            curl_bin = "curl.exe" if os.name == "nt" else "curl"
            cp = subprocess.run(
                [curl_bin, "-k", "-s", "-o", os.devnull, "-w", "%{http_code}", fallback_url],
                capture_output=True, text=True, timeout=60,
            )
            fb_code = (cp.stdout or "").strip()
            print(f"[verify-get] GET {fallback_url} -> {fb_code}")
        if fb_code == "200":
            final_url = fallback_url
            code = fb_code

    local_size = os.path.getsize(local_zip)
    print("=" * 60)
    print(f"ZIP_NAME={zip_name}")
    print(f"DOWNLOAD_URL={final_url}")
    print(f"HTTP_STATUS={code}")
    print(f"LOCAL_SIZE={local_size}")
    print(f"REMOTE_SIZE={remote_size}")
    print("=" * 60)
    if code != "200":
        sys.exit(2)


if __name__ == "__main__":
    main()
