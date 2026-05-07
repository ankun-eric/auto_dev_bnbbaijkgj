"""[BUG-FIX-RESCHEDULE-V2 2026-05-07] 微信小程序打包并上传到服务器"""
from __future__ import annotations

import os
import time
import secrets
import zipfile
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_ROOT = Path(__file__).parent
MP_DIR = PROJ_ROOT / "miniprogram"

ts = time.strftime("%Y%m%d_%H%M%S")
rnd = secrets.token_hex(2)
zip_name = f"miniprogram_bug403_{ts}_{rnd}.zip"
zip_path = PROJ_ROOT / zip_name


def pack_zip():
    print(f"[PACK] {zip_path}")
    excluded_dirs = {"node_modules", ".git", "miniprogram_npm"}
    excluded_suffixes = {".zip", ".log"}
    count = 0
    size = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for f in files:
                fp = Path(root) / f
                if fp.suffix.lower() in excluded_suffixes:
                    continue
                arc = fp.relative_to(MP_DIR.parent)
                zf.write(fp, arc.as_posix())
                count += 1
                size += fp.stat().st_size
    print(f"[PACK] {count} files, {size/1024:.1f} KB source size")
    print(f"[PACK] zip size: {zip_path.stat().st_size/1024:.1f} KB")


def upload():
    print(f"\n[SSH] connecting {HOST}...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        # 历史 PRD-365 / PRD-370 / BUG-FIX-REBUY-V1 / BUG-401 验证通过的路径：
        #  /home/ubuntu/{DID}/static/miniprogram/{zip}
        #  对外访问：{base_url}/miniprogram/{zip}
        remote_static_dir = f"/home/ubuntu/{DID}/static/miniprogram"
        remote_path = f"{remote_static_dir}/{zip_name}"
        chan = c.get_transport().open_session()
        chan.exec_command(f"mkdir -p {remote_static_dir}")
        chan.recv_exit_status()
        sftp = c.open_sftp()
        sftp.put(str(zip_path), remote_path)
        sftp.close()
        print(f"[SCP] uploaded -> {remote_path}")
        url = f"https://newbb.test.bangbangvip.com/autodev/{DID}/miniprogram/{zip_name}"
        chan = c.get_transport().open_session()
        chan.exec_command(f"curl -sI -o /dev/null -w 'HEAD=%{{http_code}}\\nurl={url}\\n' '{url}'")
        chan.recv_exit_status()
        out = chan.makefile().read().decode()
        print(out)
        return url
    finally:
        c.close()


def main():
    pack_zip()
    url = upload()
    print(f"\n=== DONE ===\nDownload URL: {url}")


if __name__ == "__main__":
    main()
