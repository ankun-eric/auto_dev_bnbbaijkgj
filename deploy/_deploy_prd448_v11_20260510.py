"""[PRD-448 v1.1] 增量补丁部署脚本 — 咨询人胶囊二次细化

将 H5-web 端 AdvisorCapsule 组件 v1.1 视觉/行为升级部署到测试服务器：
- 新增 ArrowIcon（SVG 箭头取代字符 ⌄/⌃）
- 调整字号 14 / 行高 20 / 内边距 6×12 / 圆角 10
- 本人 (consultantId=0) 也渲染胶囊
- 详情页 profile_row_enabled 兜底为 true
- 加载中/空时整条胶囊不渲染（不再显示占位）

仅改 h5-web。后端 / admin-web / 小程序 / app 无需重建。
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
    ("h5-web/src/components/ai-chat/AdvisorCapsule/index.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/AdvisorCapsule/index.tsx"),
    ("h5-web/src/components/ai-chat/AdvisorCapsule/PersonIcon.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/AdvisorCapsule/PersonIcon.tsx"),
    ("h5-web/src/components/ai-chat/AdvisorCapsule/ArrowIcon.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/AdvisorCapsule/ArrowIcon.tsx"),
    ("h5-web/src/components/ai-chat/ProfileCard.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/ProfileCard.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/app/chat/[sessionId]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/chat/[sessionId]/page.tsx"),
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
        remote_dir = remote.rsplit("/", 1)[0]
        cli.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(str(local_path), remote)
        print(f"[UPLOAD] {local_rel} -> {remote}")
    sftp.close()


def main() -> int:
    cli = ssh_connect()
    try:
        rc, _, _ = run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        upload_files(cli)
        # 仅 h5-web 容器需要重建（前端组件源码变更）
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=1800)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)
        time.sleep(12)
        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/login",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/chat/1",
            f"{BASE_URL}/health-archive",
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
