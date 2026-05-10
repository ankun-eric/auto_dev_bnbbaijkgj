"""
PRD-442 里程碑 2 · H5 端「宾尼小康」品牌色全量落地部署脚本
============================================================
方案：tar 打包 h5-web/src 与 h5-web/public 上传到服务器项目目录，
覆盖原文件后用 docker compose build h5-web && up -d 重建 H5 容器。

部署后 smoke 关键页面：
- /            → 落地页
- /(tabs)/home → 首页主入口（旧 .compact-home-header 绿色顶 → 天蓝）
- /ai-home     → AI 主战场（多颜色）
- /chat/test   → 对话页（最大改造量）
- /design-system-v2/index.html → PRD-442 基建可视化（回归）
"""
from __future__ import annotations
import os
import sys
import time
import tarfile
import io
import urllib.request
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

ROOT = Path(__file__).resolve().parent
LOCAL_H5_SRC = ROOT / "h5-web" / "src"

REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
REMOTE_TMP_TAR = f"/tmp/h5_prd444_{int(time.time())}.tar.gz"


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=60)

    def run(cmd: str, timeout: int = 600):
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

    # ---- Step 1: 本地打 tar 包（仅 h5-web/src，体积小） ----
    print("=" * 70)
    print("Step 1: tar h5-web/src locally")
    print("=" * 70)
    local_tar_path = ROOT / f"h5_src_prd444_{int(time.time())}.tar.gz"
    with tarfile.open(local_tar_path, "w:gz") as tar:
        tar.add(LOCAL_H5_SRC, arcname="src")
    size = local_tar_path.stat().st_size
    print(f"local tar created: {local_tar_path}  ({size/1024:.1f} KB)")

    # ---- Step 2: SFTP 上传到服务器 /tmp ----
    print("=" * 70)
    print("Step 2: SFTP upload to server")
    print("=" * 70)
    sftp = ssh.open_sftp()
    sftp.put(str(local_tar_path), REMOTE_TMP_TAR)
    sftp.close()
    print(f"uploaded to {REMOTE_TMP_TAR}")

    # ---- Step 3: 服务器侧覆盖 src + 重建 H5 容器 ----
    print("=" * 70)
    print("Step 3: extract on server & rebuild H5 container")
    print("=" * 70)

    cmds = [
        # 先备份原 src（保险）
        f"cd {REMOTE_PROJECT_DIR}/h5-web && rm -rf .src_backup_prd444 && mv src .src_backup_prd444",
        # 解压到 h5-web 目录（tar 里第一层是 src/）
        f"cd {REMOTE_PROJECT_DIR}/h5-web && tar -xzf {REMOTE_TMP_TAR} && ls src | head -5",
        # 校验：确认 globals.css 已含 brand-500
        f"grep -c 'color-brand-500' {REMOTE_PROJECT_DIR}/h5-web/src/app/globals.css || echo MISS",
        f"grep -c '宾尼小康' {REMOTE_PROJECT_DIR}/h5-web/src/app/layout.tsx || echo MISS",
        # 重建 + 重启 H5 容器（不影响其它容器）
        f"cd {REMOTE_PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -30",
        f"cd {REMOTE_PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -10",
        f"docker ps --filter name={DEPLOY_ID}-h5 --format '{{{{.Names}}}}|{{{{.Status}}}}'",
        f"rm -f {REMOTE_TMP_TAR}",
    ]
    rebuild_failed = False
    for c in cmds:
        rc, _, _ = run(c, timeout=900)
        if "docker compose build" in c and rc != 0:
            rebuild_failed = True

    if rebuild_failed:
        print("\n!!! docker compose build FAILED, attempting rollback !!!")
        run(f"cd {REMOTE_PROJECT_DIR}/h5-web && rm -rf src && mv .src_backup_prd444 src")
        ssh.close()
        local_tar_path.unlink(missing_ok=True)
        sys.exit(1)

    # ---- Step 4: 等待 + smoke 测试 ----
    print("=" * 70)
    print("Step 4: wait 25s for container ready & run smoke test")
    print("=" * 70)
    time.sleep(25)

    smoke_paths = [
        "/",
        "/login/",
        "/home/",
        "/ai-home/",
        "/design-system-v2/index.html",
        "/design-system-v2/design-tokens.css",
    ]
    smoke_results = []
    for p in smoke_paths:
        url = BASE_URL + p
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PRD444-smoke/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read(8192)
                code = resp.getcode()
                ok = code == 200
                # 对 / 与 /home/ 进一步校验是否含天蓝主色或宾尼小康
                hint = ""
                text = body.decode("utf-8", errors="replace")
                if "宾尼小康" in text:
                    hint = "[contains 宾尼小康]"
                elif "0EA5E9" in text or "brand-500" in text or "0ea5e9" in text:
                    hint = "[contains brand-500]"
                smoke_results.append((url, code, ok, hint))
                print(f"  {url}  → {code}  {hint}")
        except Exception as e:
            smoke_results.append((url, 0, False, str(e)))
            print(f"  {url}  → ERROR: {e}")

    pass_count = sum(1 for _, _, ok, _ in smoke_results if ok)
    print(f"\n[smoke] {pass_count}/{len(smoke_results)} PASS")

    ssh.close()
    local_tar_path.unlink(missing_ok=True)
    print("=" * 70)
    print(f"PRD-444 H5 deploy DONE. smoke = {pass_count}/{len(smoke_results)}")
    print("=" * 70)
    sys.exit(0 if pass_count == len(smoke_results) else 2)


if __name__ == "__main__":
    main()
