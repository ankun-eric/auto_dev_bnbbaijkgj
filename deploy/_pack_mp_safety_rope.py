"""[PRD-SAFETY-ROPE-V1 2026-06-03] 小程序打包 zip + SFTP 上传

输出：miniprogram_safety_rope_<timestamp>_<rand>.zip
上传到：服务器静态目录，可通过 BASE_URL/<file>.zip 浏览器下载
"""
import os
import shutil
import zipfile
import secrets
import time
import paramiko

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MP_DIR = os.path.join(ROOT, "miniprogram")
TS = time.strftime("%Y%m%d_%H%M%S")
RAND = secrets.token_hex(2)
ZIP_NAME = f"miniprogram_safety_rope_{TS}_{RAND}.zip"
OUT = os.path.join(ROOT, ZIP_NAME)

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# 不打包的文件 / 目录
EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".cache", "miniprogram_npm"}
EXCLUDE_FILES = {".DS_Store"}


def main():
    print(f"[1/3] Zip {MP_DIR} → {OUT}")
    if os.path.exists(OUT):
        os.remove(OUT)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, ROOT)
                zf.write(full, rel)
    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f"  ✓ zip size = {size_mb:.2f} MB")

    print(f"[2/3] SFTP upload → {HOST}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()
    # 服务器路径：上传到 ~/<deploy_id>/uploads 目录，然后 docker cp 到 gateway-nginx 的 /data/static/apk
    remote_tmp = f"/home/ubuntu/{DID}/{ZIP_NAME}"
    sftp.put(OUT, remote_tmp)
    sftp.close()
    print(f"  ✓ uploaded to {remote_tmp}")

    # 把文件复制到 gateway-nginx 容器内的 /data/static/apk/ 下载目录
    def sh(cmd, t=60):
        _, so, se = c.exec_command(cmd, timeout=t)
        out = so.read().decode("utf-8", "ignore")
        err = se.read().decode("utf-8", "ignore")
        if out: print(out[-500:])
        if err: print("ERR:", err[-300:])

    sh(f"docker cp {remote_tmp} gateway-nginx:/data/static/apk/{ZIP_NAME}")

    print("[3/3] Verify download URL")
    download_url = f"https://newbb.test.bangbangvip.com/autodev/{DID}/downloads/{ZIP_NAME}"
    sh(f"curl -sk -o /dev/null -w 'download=%{{http_code}}\\n' {download_url}")
    c.close()

    # 清理本地 zip
    print(f"\n[DONE] Download URL: {download_url}")
    print(f"       Local zip: {OUT}")
    # 写入文件名记录
    with open(os.path.join(ROOT, "_mp_safety_rope_url.txt"), "w") as f:
        f.write(download_url)


if __name__ == "__main__":
    main()
