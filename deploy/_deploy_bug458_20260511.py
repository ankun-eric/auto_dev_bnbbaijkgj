"""[BUG-458] 部署脚本 — AI 对话首页·左侧抽屉页·顶栏左上角账号信息与头像未同行 修复

仅改动 H5 端：
- h5-web/src/components/ai-chat/Sidebar.tsx
  顶栏由「头像+图标 / 昵称 / ID 胶囊」三行纵向堆叠，
  重构为单行水平 Flex：头像 + 名片块（昵称+ID 纵向） + 顶栏图标组（铃铛+设置）。
  同时取消 ID 胶囊点击复制（仅纯展示）。

部署流程：
1. SFTP 上传修改后的 Sidebar.tsx 到服务器
2. docker compose build h5-web（仅前端容器）
3. docker compose up -d h5-web
4. curl 验证关键页面 200/3xx
5. 远端源码 grep BUG-458 关键标记，确认源码已生效
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
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=1800)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)

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
            f"{BASE_URL}/ai-settings",
        ]
        bad = []
        for u in urls:
            rc, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            if not (
                code.startswith("2")
                or code.startswith("3")
                or code in {"401", "403"}
            ):
                bad.append((u, code))

        # 远端源码标记验证
        rc, out, _ = run(
            cli,
            f"grep -c 'BUG-458' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        bug458_marker = (out or "").strip()
        print(f"[VERIFY] BUG-458 markers in remote source: {bug458_marker}")

        # 检查 bh-user-nameblock testid 是否进入 .next 产物
        rc, out, _ = run(
            cli,
            "docker exec "
            f"{DEPLOY_ID}-h5 "
            "sh -c 'grep -rl \"bh-user-nameblock\" /app/.next 2>/dev/null | head -3 || echo NONE'",
        )
        print(f"[VERIFY] bh-user-nameblock marker in .next: {out.strip()[:300]}")

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
