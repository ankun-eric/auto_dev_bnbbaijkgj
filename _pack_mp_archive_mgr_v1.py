"""[PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 小程序打包脚本（采用既有路径约定）

打包 → SSH 上传到 /home/ubuntu/<deploy_id>/static/miniprogram/ → 验证 URL
下载 URL 形式：{BASE_URL}/miniprogram/<file>.zip
"""
from __future__ import annotations
import os
import sys
import time
import secrets
import zipfile
from pathlib import Path
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

ts = time.strftime("%Y%m%d_%H%M%S")
rand = secrets.token_hex(2)
ZIP_NAME = f"miniprogram_archive_mgr_{ts}_{rand}.zip"

ROOT = Path(__file__).resolve().parent
MP_DIR = ROOT / "miniprogram"
LOCAL_ZIP = ROOT / ZIP_NAME

REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
REMOTE_ZIP = f"{REMOTE_DIR}/{ZIP_NAME}"


def make_zip():
    print(f"[pack] creating {ZIP_NAME} from {MP_DIR} ...")
    if LOCAL_ZIP.exists():
        LOCAL_ZIP.unlink()
    with zipfile.ZipFile(LOCAL_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__")]
            for fn in files:
                if fn.endswith(".log"):
                    continue
                full = Path(root) / fn
                arc = full.relative_to(MP_DIR.parent)  # 顶层目录 = miniprogram/
                z.write(full, arcname=str(arc))
    sz = LOCAL_ZIP.stat().st_size / 1024 / 1024
    print(f"[pack] zip size = {sz:.2f} MB")


def ssh():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, 22, USER, PASS, timeout=30,
                look_for_keys=False, allow_agent=False)
    return cli


def run(cli, cmd, sudo=False, check=True, t=120, quiet=False):
    full = cmd
    if sudo:
        full = f"echo '{PASS}' | sudo -S bash -lc '{cmd}'"
    if not quiet:
        print(f"$ {cmd[:240]}")
    _, sout, serr = cli.exec_command(full, timeout=t)
    out = sout.read().decode(errors="replace")
    err = serr.read().decode(errors="replace")
    rc = sout.channel.recv_exit_status()
    if not quiet:
        if out.strip():
            print(out[-1500:])
        if err.strip():
            print("[stderr]", err[-1000:])
    if check and rc != 0:
        raise RuntimeError(f"cmd failed: {cmd}")
    return rc, out, err


def main():
    make_zip()
    cli = ssh()
    try:
        # 确保远端目录存在
        run(cli, f"mkdir -p {REMOTE_DIR}")
        # 上传
        sftp = cli.open_sftp()
        print(f"[pack] sftp {LOCAL_ZIP} → {REMOTE_ZIP}")
        sftp.put(str(LOCAL_ZIP), REMOTE_ZIP)
        sftp.close()

        url = f"{BASE_URL}/miniprogram/{ZIP_NAME}"
        print(f"[pack] verifying {url}")
        time.sleep(1)
        rc, out, _ = run(
            cli,
            f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'",
            check=False, quiet=False
        )
        code = out.strip()
        print(f"[pack] HTTP {code}")
        Path(ROOT / "_mp_archive_mgr_url.txt").write_text(url + "\n", encoding="utf-8")
        print(f"\n[pack] FINAL ZIP URL: {url}")
        if "200" not in code:
            print("[pack] !! 下载验证未 200，可能 nginx 路由仍 cache 中，请手工再 curl 一次")
            sys.exit(1)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
