"""[BUGFIX V1 2026-06-03] 小程序打包 zip + SFTP 上传 + 网关静态目录

本次小程序端改动:
- miniprogram/pages/health-profile/index.wxss
  (Hero 卡片下「邀请守护」按钮配色由蓝色改为橙色渐变 + 白字,与 H5 端对齐)

输出: miniprogram_bugfix_v1_<timestamp>_<rand>.zip
访问: https://newbb.test.bangbangvip.com/autodev/<DID>/downloads/<file>.zip
"""
import os
import sys
import zipfile
import secrets
import time
import paramiko

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MP_DIR = os.path.join(ROOT, "miniprogram")
TS = time.strftime("%Y%m%d_%H%M%S")
RAND = secrets.token_hex(2)
ZIP_NAME = f"miniprogram_bugfix_v1_{TS}_{RAND}.zip"
OUT = os.path.join(ROOT, ZIP_NAME)

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".cache", "miniprogram_npm"}
EXCLUDE_FILES = {".DS_Store"}


def main():
    print(f"[1/3] Zip {MP_DIR} -> {OUT}")
    if not os.path.isdir(MP_DIR):
        print(f"ERROR: miniprogram dir not found: {MP_DIR}")
        sys.exit(1)
    if os.path.exists(OUT):
        os.remove(OUT)
    file_count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, ROOT)
                zf.write(full, rel)
                file_count += 1
    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f"  OK zip size = {size_mb:.2f} MB, files = {file_count}")

    print(f"[2/3] SFTP upload -> {HOST}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    def sh(cmd, t=60):
        _, so, se = c.exec_command(cmd, timeout=t)
        out = so.read().decode("utf-8", "ignore")
        err = se.read().decode("utf-8", "ignore")
        if out:
            print(out[-500:])
        if err:
            print("ERR:", err[-300:])
        return out, err

    sh(f"mkdir -p /home/ubuntu/{DID}")
    sftp = c.open_sftp()
    remote_tmp = f"/home/ubuntu/{DID}/{ZIP_NAME}"
    sftp.put(OUT, remote_tmp)
    sftp.close()
    print(f"  OK uploaded to {remote_tmp}")

    sh(f"docker cp {remote_tmp} gateway-nginx:/data/static/apk/{ZIP_NAME}")

    print("[3/3] Verify download URL")
    download_url = f"https://newbb.test.bangbangvip.com/autodev/{DID}/downloads/{ZIP_NAME}"
    out, _ = sh(f"curl -sk -o /dev/null -w 'download=%{{http_code}}\\n' {download_url}")
    c.close()

    http_code = ""
    for line in out.splitlines():
        if line.startswith("download="):
            http_code = line.split("=", 1)[1].strip()
            break

    print(f"\n[DONE]")
    print(f"  ZIP_NAME    = {ZIP_NAME}")
    print(f"  DOWNLOAD_URL= {download_url}")
    print(f"  HTTP_CODE   = {http_code}")

    with open(os.path.join(ROOT, "_mp_bugfix_v1_url.txt"), "w", encoding="utf-8") as f:
        f.write(download_url + "\n")
    with open(os.path.join(ROOT, "_mp_bugfix_v1_zipname.txt"), "w", encoding="utf-8") as f:
        f.write(ZIP_NAME + "\n")


if __name__ == "__main__":
    main()
