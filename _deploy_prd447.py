"""PRD-447 v2 · AI 对话模式方案 A 全量落地 部署脚本

- tar 打包 h5-web/src + backend/app + admin-web/src 上传服务器
- 服务器侧覆盖三端源码 → docker compose build h5-web backend admin-web → up -d
- smoke 测试关键页面 + 后端 themes API
"""
from __future__ import annotations

import io
import os
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

ROOT = Path(__file__).resolve().parent
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
TS = int(time.time())
REMOTE_TMP_TAR = f"/tmp/prd447_full_{TS}.tar.gz"


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=60)

    def run(cmd: str, timeout: int = 900):
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(f"\n$ {cmd[:160]}")
        print(f"[rc={rc}]")
        if out:
            print(out[:2500])
        if err:
            print("ERR:", err[:1500])
        return rc, out, err

    # ---- Step 1: 本地打 tar ----
    print("=" * 70)
    print("Step 1: tar (h5-web/src + backend/app + admin-web/src)")
    print("=" * 70)
    local_tar = ROOT / f"prd447_full_{TS}.tar.gz"
    with tarfile.open(local_tar, "w:gz") as tar:
        tar.add(ROOT / "h5-web" / "src", arcname="h5-web/src")
        tar.add(ROOT / "backend" / "app", arcname="backend/app")
        tar.add(ROOT / "admin-web" / "src", arcname="admin-web/src")
    size = local_tar.stat().st_size
    print(f"local tar: {local_tar}  ({size/1024/1024:.2f} MB)")

    # ---- Step 2: SFTP 上传 ----
    print("=" * 70)
    print("Step 2: SFTP upload")
    print("=" * 70)
    sftp = ssh.open_sftp()
    sftp.put(str(local_tar), REMOTE_TMP_TAR)
    sftp.close()
    print(f"uploaded → {REMOTE_TMP_TAR}")

    # ---- Step 3: 服务器解包 + 重建 ----
    print("=" * 70)
    print("Step 3: extract & rebuild containers")
    print("=" * 70)
    cmds = [
        # 备份
        f"cd {REMOTE_PROJECT_DIR} && rm -rf .prd447_backup && mkdir .prd447_backup",
        f"cd {REMOTE_PROJECT_DIR} && cp -r h5-web/src .prd447_backup/h5_src && cp -r backend/app .prd447_backup/backend_app && cp -r admin-web/src .prd447_backup/admin_src",
        # 解压（覆盖）
        f"cd {REMOTE_PROJECT_DIR} && tar -xzf {REMOTE_TMP_TAR}",
        # 验证
        f"grep -c 'PRD-447 v2' {REMOTE_PROJECT_DIR}/h5-web/src/app/globals.css || echo MISS_GLOBALS",
        f"grep -c 'themes' {REMOTE_PROJECT_DIR}/backend/app/main.py || echo MISS_MAIN",
        f"ls {REMOTE_PROJECT_DIR}/h5-web/src/components/design-system | head -20",
        # 重建
        f"cd {REMOTE_PROJECT_DIR} && docker compose build h5-web backend admin-web 2>&1 | tail -50",
        f"cd {REMOTE_PROJECT_DIR} && docker compose up -d h5-web backend admin-web 2>&1 | tail -10",
        f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}|{{{{.Status}}}}'",
        f"rm -f {REMOTE_TMP_TAR}",
    ]
    rebuild_failed = False
    for c in cmds:
        rc, out, _ = run(c, timeout=1200)
        if "docker compose build" in c and rc != 0:
            rebuild_failed = True

    if rebuild_failed:
        print("\n!!! rebuild FAILED, rolling back !!!")
        run(f"cd {REMOTE_PROJECT_DIR} && rm -rf h5-web/src backend/app admin-web/src && cp -r .prd447_backup/h5_src h5-web/src && cp -r .prd447_backup/backend_app backend/app && cp -r .prd447_backup/admin_src admin-web/src && docker compose up -d h5-web backend admin-web")
        ssh.close()
        local_tar.unlink(missing_ok=True)
        sys.exit(1)

    # ---- Step 4: smoke ----
    print("=" * 70)
    print("Step 4: wait 35s & smoke test")
    print("=" * 70)
    time.sleep(35)

    smoke_paths = [
        "/",
        "/login/",
        "/home/",
        "/ai-home/",
        "/design-system-v2-preview/",
        "/design-system-v2/index.html",
        "/api/h5/active-theme",
        "/api/admin/themes?page=1&size=10",
    ]
    pass_count = 0
    for p in smoke_paths:
        url = BASE_URL + p
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PRD447-smoke/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                code = resp.getcode()
                ok = code == 200
                if ok:
                    pass_count += 1
                print(f"  {url}  → {code}  {'PASS' if ok else 'FAIL'}")
        except Exception as e:
            print(f"  {url}  → ERROR: {e}")

    print(f"\n[smoke] {pass_count}/{len(smoke_paths)} PASS")

    ssh.close()
    local_tar.unlink(missing_ok=True)
    print("=" * 70)
    print(f"PRD-447 deploy DONE. smoke = {pass_count}/{len(smoke_paths)}")
    print("=" * 70)
    sys.exit(0 if pass_count >= len(smoke_paths) - 1 else 2)


if __name__ == "__main__":
    main()
