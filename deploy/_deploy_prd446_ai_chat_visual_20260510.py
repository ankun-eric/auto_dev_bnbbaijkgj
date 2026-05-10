"""[PRD-442 AI 对话模式页面修复 v1.0] 部署脚本（任务 446）

将 H5 端 AI 对话模式相关页面（共 20 屏）的视觉修复（晴空诊室主色调一致性）
部署到测试服务器，并验证关键链接 HTTP 200。

只改 h5-web，前端仅样式与极少 TSX 容器/类名调整。后端 / admin-web / 小程序无需重建。
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
    # 全局样式 + theme
    ("h5-web/src/app/globals.css",
     f"{REMOTE_PROJ}/h5-web/src/app/globals.css"),
    ("h5-web/src/lib/theme.ts",
     f"{REMOTE_PROJ}/h5-web/src/lib/theme.ts"),
    # (ai-chat) 路由组 layout
    ("h5-web/src/app/(ai-chat)/layout.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/(ai-chat)/layout.tsx"),
    ("h5-web/src/app/(ai-chat)/medication-plans/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/(ai-chat)/medication-plans/page.tsx"),
    # 独立 AI 对话页面
    ("h5-web/src/app/chat/[sessionId]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/chat/[sessionId]/page.tsx"),
    ("h5-web/src/app/drug/chat/[sessionId]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/drug/chat/[sessionId]/page.tsx"),
    ("h5-web/src/app/customer-service/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/customer-service/page.tsx"),
    ("h5-web/src/app/shared/chat/[token]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/shared/chat/[token]/page.tsx"),
    ("h5-web/src/app/shared/drug/[token]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/shared/drug/[token]/page.tsx"),
    ("h5-web/src/app/shared/report/[token]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/shared/report/[token]/page.tsx"),
    ("h5-web/src/app/tcm/result/[id]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/tcm/result/[id]/page.tsx"),
    ("h5-web/src/app/tcm/diagnosis/[id]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/tcm/diagnosis/[id]/page.tsx"),
    ("h5-web/src/app/checkup/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/checkup/page.tsx"),
    ("h5-web/src/app/checkup/chat/[sessionId]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/checkup/chat/[sessionId]/page.tsx"),
    ("h5-web/src/app/checkup/detail/[id]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/checkup/detail/[id]/page.tsx"),
]


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 600) -> tuple[int, str, str]:
    print(f"[REMOTE] $ {cmd[:200]}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print(f"[STDERR] {err[-2000:]}")
    return rc, out, err


def upload_files(cli: paramiko.SSHClient) -> None:
    sftp = cli.open_sftp()
    for local_rel, remote in FILES:
        local_path = LOCAL_ROOT / local_rel
        if not local_path.exists():
            print(f"[SKIP] local missing: {local_path}")
            continue
        # ensure remote dir exists
        remote_dir = remote.rsplit("/", 1)[0]
        cli.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(str(local_path), remote)
        print(f"[UPLOAD] {local_rel} -> {remote}")
    sftp.close()


def main() -> int:
    cli = ssh_connect()
    try:
        # 1) ensure project dir exists
        rc, _, _ = run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        # 2) upload changed files
        upload_files(cli)
        # 3) rebuild only h5-web
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=1500)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)
        # 4) wait & verify
        time.sleep(10)
        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/login",
            f"{BASE_URL}/customer-service",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/medication-plans",
            f"{BASE_URL}/feedback",
            f"{BASE_URL}/chat-history",
            f"{BASE_URL}/account-security",
            f"{BASE_URL}/ai-settings",
            f"{BASE_URL}/health-archive",
            f"{BASE_URL}/checkup",
            f"{BASE_URL}/digital-human-call",
        ]
        bad = []
        for u in urls:
            rc, out, _ = run(cli, f"curl -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            if not code.startswith(("2", "3")):
                bad.append((u, code))
        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
