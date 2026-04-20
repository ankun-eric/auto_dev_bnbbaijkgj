"""一期体质测评 — 打包小程序 zip 并上传到服务器 static/downloads。
APK 部分走 GitHub Actions + 本地下载上传。"""
import os
import sys
import time
import zipfile

import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
STATIC_DOWNLOADS_DIR = f"{PROJECT_DIR}/static/downloads"

MP_ZIP_NAME = f"miniprogram_constitution_p1_{int(time.time())}.zip"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=180):
    print(f"\n$ {cmd[:200]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-1500:])
    if err:
        print(f"[stderr] {err[-600:]}")
    print(f"[exit {code}]")
    return code


def build_miniprogram_zip(local_root, out_path):
    mp_dir = os.path.join(local_root, "miniprogram")
    skip = {"node_modules", ".git", "miniprogram_npm"}
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        count = 0
        for root, dirs, files in os.walk(mp_dir):
            dirs[:] = [d for d in dirs if d not in skip]
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, mp_dir)
                zf.write(full, arcname=f"miniprogram/{rel.replace(os.sep, '/')}")
                count += 1
    print(f"  [mp zip] {count} files -> {out_path} ({os.path.getsize(out_path)} bytes)")


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c = connect()
    print(f"Connected to {HOST}")

    local_zip = os.path.join(local_root, MP_ZIP_NAME)
    build_miniprogram_zip(local_root, local_zip)

    run(c, f"mkdir -p {STATIC_DOWNLOADS_DIR}")
    sftp = c.open_sftp()
    remote_zip = f"{STATIC_DOWNLOADS_DIR}/{MP_ZIP_NAME}"
    sftp.put(local_zip, remote_zip)
    sftp.put(local_zip, f"{STATIC_DOWNLOADS_DIR}/miniprogram_latest.zip")
    sftp.close()
    print(f"  uploaded {os.path.getsize(local_zip)} bytes -> {remote_zip}")
    run(c, f"ls -lh {STATIC_DOWNLOADS_DIR}/miniprogram_latest.zip {remote_zip}")

    os.remove(local_zip)

    print("\n=== DONE ===")
    print(f"  小程序 zip(固定版): https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/{MP_ZIP_NAME}")
    print(f"  小程序 zip(最新):   https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/miniprogram_latest.zip")

    c.close()
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
