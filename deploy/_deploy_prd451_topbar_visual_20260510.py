"""[PRD-451 AI 主页顶栏视觉融合优化 v1.0] 部署脚本（任务 451）

将 H5 端 AI 主页（/ai-home）顶栏视觉融合优化（背景色与内容区统一 + 标题与汉堡菜单间距收紧到 3px）
部署到测试服务器，并验证关键链接 HTTP 200。

只改 h5-web/src/app/(ai-chat)/ai-home/page.tsx 一个文件，仅样式（CSS 内联属性）调整：
- 顶栏 background: var(--color-primary) -> THEME.background
- 标题 paddingLeft: 4 -> 3

后端 / admin-web / 小程序无需重建。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
]


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 600) -> tuple[int, str, str]:
    print(f"[REMOTE] $ {cmd[:200]}", flush=True)
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:], flush=True)
    if err.strip():
        print(f"[STDERR] {err[-2000:]}", flush=True)
    return rc, out, err


def upload_files(cli: paramiko.SSHClient) -> None:
    sftp = cli.open_sftp()
    for local_rel, remote in FILES:
        local_path = LOCAL_ROOT / local_rel
        if not local_path.exists():
            print(f"[SKIP] local missing: {local_path}", flush=True)
            continue
        remote_dir = remote.rsplit("/", 1)[0]
        cli.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(str(local_path), remote)
        print(f"[UPLOAD] {local_rel} -> {remote}", flush=True)
    sftp.close()


def main() -> int:
    cli = ssh_connect()
    try:
        # 1) ensure project dir exists
        rc, out, _ = run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        if "MISSING" in out:
            print("[ERROR] remote project dir missing", flush=True)
            return 2

        # 2) upload changed files
        upload_files(cli)

        # 3) rebuild only h5-web
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=1800)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)

        # 4) wait & verify
        time.sleep(12)
        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/login",
        ]
        bad = []
        for u in urls:
            rc, out, _ = run(cli, f"curl -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}", flush=True)
            if not code.startswith(("2", "3")):
                bad.append((u, code))
        print(f"[SUMMARY] failed urls = {bad}", flush=True)
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
