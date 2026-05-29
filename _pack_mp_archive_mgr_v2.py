"""[PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 小程序打包 v2 —— 通过 backend /uploads/ 路由暴露

策略：
- gateway-nginx 既有 location /autodev/<id>/uploads/ → backend:8000/uploads/
- backend Dockerfile 已配置 /app/uploads 卷
- 把 zip docker cp 到 backend:/app/uploads/<zip>
- 通过 https://<base>/uploads/<zip> 下载
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
                arc = full.relative_to(MP_DIR.parent)  # miniprogram/
                z.write(full, arcname=str(arc))
    sz = LOCAL_ZIP.stat().st_size / 1024 / 1024
    print(f"[pack] zip size = {sz:.2f} MB")


def ssh():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, 22, USER, PASS, timeout=30,
                look_for_keys=False, allow_agent=False)
    return cli


def run(cli, cmd, sudo=False, check=True, t=120):
    full = cmd
    if sudo:
        full = f"echo '{PASS}' | sudo -S bash -lc '{cmd}'"
    print(f"$ {cmd[:240]}")
    _, sout, serr = cli.exec_command(full, timeout=t)
    out = sout.read().decode(errors="replace")
    err = serr.read().decode(errors="replace")
    rc = sout.channel.recv_exit_status()
    if out.strip():
        print(out[-1200:])
    if err.strip() and "sudo" not in err[:50]:
        print("[err]", err[-600:])
    if check and rc != 0:
        raise RuntimeError(f"cmd failed: {cmd}")
    return rc, out, err


def main():
    make_zip()
    cli = ssh()
    try:
        host_dir = f"/home/ubuntu/{DEPLOY_ID}"
        host_zip = f"{host_dir}/{ZIP_NAME}"
        sftp = cli.open_sftp()
        print(f"[pack] sftp {LOCAL_ZIP} → {host_zip}")
        sftp.put(str(LOCAL_ZIP), host_zip)
        sftp.close()

        be = f"{DEPLOY_ID}-backend"
        # 确保 uploads 目录存在并 cp 进去
        run(cli, f"docker exec {be} mkdir -p /app/uploads", sudo=True, check=False)
        run(cli, f"docker cp {host_zip} {be}:/app/uploads/{ZIP_NAME}", sudo=True)
        # 验证 backend 容器内能看到
        run(cli, f"docker exec {be} ls -la /app/uploads/{ZIP_NAME}", sudo=True)

        # 验证 URL（走 nginx /uploads/ 路由 → backend:8000/uploads/）
        # 但 backend 端不一定有 GET /uploads/* 端点，需要检查
        # 我们直接试一下
        url = f"{BASE_URL}/uploads/{ZIP_NAME}"
        print(f"[pack] verifying {url}")
        time.sleep(2)
        rc, out, _ = run(cli, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", check=False)
        code = out.strip()
        print(f"[pack] HTTP {code}")

        if "200" not in code:
            print("[pack] backend 没有 /uploads/<file> 静态服务，改用 h5-web public 方案")
            # 把 zip 放进 h5 容器的 /app/public/<zip>
            h5 = f"{DEPLOY_ID}-h5"
            run(cli, f"docker cp {host_zip} {h5}:/app/public/{ZIP_NAME}", sudo=True, check=False)
            url2 = f"{BASE_URL}/{ZIP_NAME}"
            time.sleep(2)
            rc2, out2, _ = run(cli, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url2}'", check=False)
            print(f"[pack] try h5 public URL: {url2} → {out2.strip()}")
            if "200" in out2:
                url = url2
                code = "200"

        print(f"\n[pack] FINAL ZIP URL: {url} (HTTP {code})")
        Path(ROOT / "_mp_archive_mgr_url.txt").write_text(url + "\n", encoding="utf-8")
        if "200" not in code:
            sys.exit(1)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
