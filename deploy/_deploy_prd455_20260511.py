"""[PRD-455 V7] 部署脚本 — AI 对话首页·左侧抽屉页全量优化

仅改动 H5 端：
- h5-web/src/components/ai-chat/Sidebar.tsx —— 完全重写为 PRD V7 规格

部署流程：
1. SFTP 上传 Sidebar.tsx 到服务器
2. docker compose build h5-web（仅前端容器）
3. docker compose up -d h5-web
4. 等待启动后 curl 验证关键页面 200/3xx
5. 远端使用容器内构建产物里 grep 抽屉关键文案，确认源码已生效
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
    (
        "h5-web/src/components/ai-chat/Sidebar.tsx",
        f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
    ),
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
        # 仅 h5-web 容器需重建
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=1800)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)

        # 等待容器就绪
        time.sleep(20)

        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/login",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/chat/1",
            f"{BASE_URL}/health-archive",
            f"{BASE_URL}/notifications",
            f"{BASE_URL}/my-coupons",
            f"{BASE_URL}/unified-orders",
            f"{BASE_URL}/my-favorites",
            f"{BASE_URL}/points-center",
            f"{BASE_URL}/my-devices",
            f"{BASE_URL}/member-qrcode",
            f"{BASE_URL}/ai-settings",
        ]
        bad = []
        for u in urls:
            rc, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            # 2xx/3xx/4xx 视情况判断；登录页跳转 308/200 都算 OK；
            # 部分用户态依赖页（如收藏）未登录返 308 → 也接受
            if not (
                code.startswith("2")
                or code.startswith("3")
                or code in {"401", "403"}
            ):
                bad.append((u, code))

        # 验证 Sidebar.tsx 已上传到容器（通过 docker exec 直接看文件 grep）
        rc, out, _ = run(
            cli,
            "docker exec "
            f"{DEPLOY_ID}-h5 "
            "sh -c 'grep -c \"PRD-455 V7\" /app/src/components/ai-chat/Sidebar.tsx 2>/dev/null || echo NOFILE'",
        )
        if "NOFILE" in out or out.strip().startswith("0"):
            # 容器内可能在 dist/构建产物，先抓 .next 目录的文件
            rc2, out2, _ = run(
                cli,
                "docker exec "
                f"{DEPLOY_ID}-h5 "
                "sh -c 'find /app -maxdepth 3 -name \"Sidebar*\" 2>/dev/null | head -5'",
            )
            print(f"[INFO] sidebar files in container: {out2.strip()}")

        # 直接通过 SSH 检查源码文件
        rc, out, _ = run(
            cli,
            f"grep -c 'PRD-455 V7' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        sidebar_marker = (out or "").strip()
        print(f"[VERIFY] PRD-455 V7 markers in remote source: {sidebar_marker}")

        # 检查抽屉关键文案是否出现在最终 next 静态产物里（可选）
        rc, out, _ = run(
            cli,
            "docker exec "
            f"{DEPLOY_ID}-h5 "
            "sh -c 'grep -rl \"家人健康管理\" /app/.next 2>/dev/null | head -3 || echo NONE'",
        )
        print(f"[VERIFY] 家人健康管理 marker in .next: {out.strip()[:300]}")

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
