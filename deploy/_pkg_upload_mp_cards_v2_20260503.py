"""[卡管理 v2.0] 打包 miniprogram + verify-miniprogram 为 zip 并上传到服务器静态目录。

输出 URL：
  https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/downloads/miniprogram_cards_v2_<ts>.zip
  https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/downloads/verify_miniprogram_cards_v2_<ts>.zip
"""
from __future__ import annotations

import os
import time
import zipfile
import paramiko
from scp import SCPClient

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
DL_DIR = f"{PROJ_DIR}/downloads"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def zip_dir(src_dir: str, zip_path: str, exclude_globs=("node_modules", ".git")):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in exclude_globs]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, src_dir)
                zf.write(full, rel)


def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    mp_zip = os.path.join(ROOT, f"miniprogram_cards_v2_{ts}.zip")
    vmp_zip = os.path.join(ROOT, f"verify_miniprogram_cards_v2_{ts}.zip")

    print(f"[1/4] 打包 miniprogram → {mp_zip}")
    zip_dir(os.path.join(ROOT, "miniprogram"), mp_zip)
    print(f"      size = {os.path.getsize(mp_zip):,} bytes")

    print(f"[2/4] 打包 verify-miniprogram → {vmp_zip}")
    zip_dir(os.path.join(ROOT, "verify-miniprogram"), vmp_zip)
    print(f"      size = {os.path.getsize(vmp_zip):,} bytes")

    print("[3/4] SSH 上传到服务器")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    ssh.exec_command(f"mkdir -p {DL_DIR}")[1].read()
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(mp_zip, DL_DIR + "/")
        scp.put(vmp_zip, DL_DIR + "/")

    print("[4/4] 验证下载链接")
    mp_name = os.path.basename(mp_zip)
    vmp_name = os.path.basename(vmp_zip)
    for name in (mp_name, vmp_name):
        cmd = (
            f"curl -ksL -o /dev/null -w '%{{http_code}} %{{size_download}}' "
            f"--max-time 30 '{BASE_URL}/downloads/{name}'"
        )
        _, stdout, _ = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode("utf-8", errors="ignore").strip()
        print(f"  {name} -> {out}")
        print(f"  URL: {BASE_URL}/downloads/{name}")
    ssh.close()
    print("\n[完成] 小程序打包上传完毕")


if __name__ == "__main__":
    main()
