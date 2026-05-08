# -*- coding: utf-8 -*-
"""[PRD-429] 上传 APK 到部署服务器并验证下载链接。"""
import os
import secrets
import datetime
import urllib.request
import urllib.error
import ssl
import sys

import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

LOCAL_APK = r"C:\auto_output\bnbbaijkgj\bini_health_android-prd429-v20260508-232412-dkhf.apk"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def main():
    if not os.path.exists(LOCAL_APK):
        print(f"ERROR: APK not found: {LOCAL_APK}")
        sys.exit(1)
    size = os.path.getsize(LOCAL_APK)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    h = secrets.token_hex(2)
    remote_name = f"bini_health_prd429_{ts}_{h}.apk"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    try:
        i, o, e = client.exec_command(f"mkdir -p {REMOTE_DIR}")
        o.channel.recv_exit_status()
        sftp = client.open_sftp()
        try:
            remote_path = f"{REMOTE_DIR}/{remote_name}"
            print(f"[upload] {LOCAL_APK} -> {remote_path} (size={size})")
            sftp.put(LOCAL_APK, remote_path)
            attr = sftp.stat(remote_path)
            print(f"[upload] OK size={attr.st_size}")
        finally:
            sftp.close()

        # SSH curl 验证
        url = f"{BASE_URL}/apk/{remote_name}"
        cmd = f'curl -sL -I -o /dev/null -w "%{{http_code}}" "{url}"'
        i, o, e = client.exec_command(cmd)
        code = o.read().decode("utf-8", errors="replace").strip()
        print(f"[curl] http_code={code}")
    finally:
        client.close()

    # 本地 HEAD 验证
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            local_code = resp.getcode()
            length = resp.headers.get("Content-Length")
            print(f"[local-head] {url} -> {local_code} length={length}")
    except urllib.error.HTTPError as ex:
        print(f"[local-head] HTTPError {ex.code}")
        local_code = ex.code

    print("=" * 60)
    print(f"APK_FILENAME={remote_name}")
    print(f"APK_DOWNLOAD_URL={url}")
    print(f"APK_SIZE={size}")
    print(f"HTTP_CODE_SSH={code}")
    print(f"HTTP_CODE_LOCAL={local_code}")

    if str(code) != "200":
        print("ERROR: SSH curl != 200")
        sys.exit(3)


if __name__ == "__main__":
    main()
