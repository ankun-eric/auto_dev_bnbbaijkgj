# -*- coding: utf-8 -*-
"""
[PRD-05 核销动作收口手机端 v1.0] 打包 verify-miniprogram 目录并上传到测试服务器静态目录。

要求：
- zip 根目录为核销小程序代码本身（解压后即可见 app.json / project.config.json），
  以便直接用「微信开发者工具」导入。
- 排除 node_modules/、.git/、*.log 等无关内容。
- 上传到 /home/ubuntu/<deployId>/static/verify-miniprogram/，
  通过 {baseUrl}/static/verify-miniprogram/<zip> HTTPS 下载。
"""
import os
import sys
import time
import secrets
import zipfile
import subprocess
import paramiko

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
MP_DIR = os.path.join(PROJECT_ROOT, "verify-miniprogram")

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
# 优先使用 gateway 已存在的静态路由 /downloads/（alias /data/static/downloads/）
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/downloads"
REMOTE_DIR_VMP = f"/home/ubuntu/{DEPLOY_ID}/static/verify-miniprogram"
URL_DOWNLOADS = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/downloads"
URL_DOWNLOADS_DIRECT = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
URL_VMP_STATIC = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/static/verify-miniprogram"

EXCLUDE_DIR_NAMES = {
    "node_modules", ".git", ".idea", ".vscode", "__pycache__", "miniprogram_npm",
}
EXCLUDE_SUFFIXES = (".log", ".DS_Store")


def build_zip_name():
    ts = time.strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    return f"verify_miniprogram_{ts}_{rand}.zip"


def should_skip(path_rel):
    parts = path_rel.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIR_NAMES:
            return True
    if path_rel.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def make_zip(zip_path):
    if not os.path.isdir(MP_DIR):
        raise RuntimeError(f"verify-miniprogram dir missing: {MP_DIR}")
    if not os.path.isfile(os.path.join(MP_DIR, "app.json")):
        raise RuntimeError("verify-miniprogram/app.json missing - cannot import to wechat devtools")
    if not os.path.isfile(os.path.join(MP_DIR, "project.config.json")):
        raise RuntimeError("verify-miniprogram/project.config.json missing")

    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]
            for fn in files:
                full = os.path.join(root, fn)
                rel_in_mp = os.path.relpath(full, MP_DIR)
                if should_skip(rel_in_mp):
                    continue
                arcname = rel_in_mp.replace("\\", "/")
                zf.write(full, arcname)
                count += 1
    print(f"[zip] wrote {count} files -> {zip_path} ({os.path.getsize(zip_path)} bytes)")


def sftp_upload(local_path, remote_paths):
    """上传到多个远程路径（先 mkdir -p）。返回首个 remote_path 的字节数。"""
    if isinstance(remote_paths, str):
        remote_paths = [remote_paths]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    first_size = 0
    try:
        sftp = ssh.open_sftp()
        try:
            for rp in remote_paths:
                rdir = os.path.dirname(rp)
                stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {rdir}")
                stdout.channel.recv_exit_status()
                sftp.put(local_path, rp)
                st = sftp.stat(rp)
                print(f"[sftp] uploaded -> {rp} ({st.st_size} bytes)")
                if not first_size:
                    first_size = st.st_size
        finally:
            sftp.close()
    finally:
        ssh.close()
    return first_size


def verify_url(url):
    curl_bin = "curl.exe" if os.name == "nt" else "curl"
    cp = subprocess.run(
        [curl_bin, "-k", "-s", "-o", os.devnull, "-w", "%{http_code}", "-I", url],
        capture_output=True, text=True, timeout=30,
    )
    code = (cp.stdout or "").strip()
    print(f"[verify] HEAD {url} -> {code}")
    return code


def try_url(url):
    code = verify_url(url)
    if code == "200":
        return code
    curl_bin = "curl.exe" if os.name == "nt" else "curl"
    cp = subprocess.run(
        [curl_bin, "-k", "-s", "-o", os.devnull, "-w", "%{http_code}", url],
        capture_output=True, text=True, timeout=60,
    )
    code = (cp.stdout or "").strip()
    print(f"[verify-get] GET {url} -> {code}")
    return code


def main():
    zip_name = build_zip_name()
    local_zip = os.path.join(PROJECT_ROOT, "deploy", zip_name)

    make_zip(local_zip)

    # 双路径上传：downloads/（已有 nginx 路由）+ verify-miniprogram/（语义路径）
    remote_zip_dl = f"{REMOTE_DIR}/{zip_name}"
    remote_zip_vmp = f"{REMOTE_DIR_VMP}/{zip_name}"
    remote_size = sftp_upload(local_zip, [remote_zip_dl, remote_zip_vmp])

    # 候选 URL，按优先级尝试
    candidates = [
        f"{URL_DOWNLOADS}/{zip_name}",          # /autodev/{id}/downloads/{zip} - 已有路由
        f"{URL_DOWNLOADS_DIRECT}/{zip_name}",   # /autodev/{id}/{zip}.zip - AUTO 直链
        f"{URL_VMP_STATIC}/{zip_name}",         # /autodev/{id}/static/verify-miniprogram/{zip} - 兜底
    ]

    final_url = candidates[0]
    code = "404"
    for url in candidates:
        c = try_url(url)
        if c == "200":
            final_url = url
            code = c
            break

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
