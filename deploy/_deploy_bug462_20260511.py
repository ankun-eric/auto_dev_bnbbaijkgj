"""[BUG-462] 部署脚本 — H5 端 AI 对话「删除历史对话提示『删除可能未同步』」修复

根因：
  前端 `h5-web/src/components/ai-chat/Sidebar.tsx` 的 `deleteOne` / `batchDelete`
  调用的是不存在的 `POST /api/chat/history/delete`，必然 4xx → 进 catch 弹
  「删除可能未同步，请稍后刷新」兜底 Toast，乐观更新让条目"视觉消失"，但
  数据库未真正删除，刷新后被删条目"复活"。

修复：
  - 单条删除：改调 `DELETE /api/chat-sessions/{id}`
  - 批量删除：改调 `POST /api/chat-sessions/batch-delete`，请求体 `session_ids: number[]`
  - 失败时立即整体回滚 `histories` 快照；批量场景额外恢复管理模式与勾选状态
  - 文案统一改为「删除失败,请稍后重试」，并带 fail 图标

仅改动单文件：
  - h5-web/src/components/ai-chat/Sidebar.tsx

部署流程：
1. SFTP 上传 Sidebar.tsx
2. docker compose build h5-web
3. docker compose up -d h5-web
4. 等容器 running，curl 验证 ai-home 路径可达
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
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
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
        run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        upload_files(cli)

        # 远端源码标记验证（BUG-462）
        _, out, _ = run(
            cli,
            f"grep -c 'BUG-462' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        marker = (out or "").strip()
        print(f"[VERIFY] BUG-462 markers in remote source: {marker}")

        # 验证新接口路径已存在于远端文件中
        _, out, _ = run(
            cli,
            f"grep -c 'chat-sessions/batch-delete' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        print(f"[VERIFY] batch-delete endpoint occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c \"api.delete(\\`/api/chat-sessions/\" {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx || true",
        )
        print(f"[VERIFY] DELETE /api/chat-sessions/{{id}} occurrences: {(out or '').strip()}")

        # 验证旧接口已彻底不存在
        _, out, _ = run(
            cli,
            f"grep -c '/api/chat/history/delete' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx || true",
        )
        old_hits = (out or "0").strip().splitlines()[-1] if out else "0"
        print(f"[VERIFY] legacy /api/chat/history/delete remaining: {old_hits} (must be 0)")

        # 构建并启动 h5-web 容器
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=2400)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)

        time.sleep(15)

        # 等容器健康
        for _ in range(24):
            rc, out, _ = run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5 2>/dev/null || echo NONE",
            )
            if (out or "").strip() == "running":
                break
            time.sleep(5)

        # smoke：H5 ai-home 页面应可达，后端 chat-sessions 应仍是 401（未登录）非 500
        urls_smoke = [
            f"{BASE_URL}/",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/api/chat-sessions",
            f"{BASE_URL}/api/chat-sessions/batch-delete",
        ]
        bad: list[tuple[str, str, str]] = []
        for u in urls_smoke:
            if u.endswith("/api/chat-sessions/batch-delete"):
                # POST 接口：用 OPTIONS 或 POST 空体验证路径存在，405/401/422/400 均说明路由已注册
                _, out, _ = run(
                    cli,
                    f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST -H 'Content-Type: application/json' -d '{{}}' {u}",
                )
            else:
                _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            if u.endswith("/api/chat-sessions"):
                if code == "500":
                    bad.append((u, code, "BACKEND_500"))
                elif code not in {"401", "403", "200"}:
                    bad.append((u, code, "UNEXPECTED"))
            elif u.endswith("/api/chat-sessions/batch-delete"):
                # 期望未登录时返回 401/403；如果返回 404 说明路由没注册（严重）
                if code in {"404"}:
                    bad.append((u, code, "NOT_FOUND"))
                elif code == "500":
                    bad.append((u, code, "BACKEND_500"))
                elif code not in {"200", "401", "403", "422", "400", "405"}:
                    bad.append((u, code, "UNEXPECTED"))
            else:
                if not (code.startswith("2") or code.startswith("3") or code in {"401", "403"}):
                    bad.append((u, code, "GENERAL"))

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
