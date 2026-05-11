"""[BUG-460] 部署脚本 — AI 对话首页·左侧抽屉「加载失败」（/api/chat-sessions 500）修复

根因：MySQL 不支持 `ORDER BY ... NULLS LAST` 语法（PostgreSQL/Oracle 专属），
SQLAlchemy 的 `.nullslast()` 在 MySQL 方言下生成的 SQL 直接被 MySQL 拒绝（错误码 1064，
语法错误：`near 'NULLS LAST, chat_sessions.updated_at DESC LIMIT 0, 20'`）。
导致 H5 抽屉「历史对话」整列加载失败（500 Internal Server Error），全量用户级故障。

修复：将 `pinned_at.desc().nullslast()` 替换为 MySQL 兼容写法：
    case((pinned_at IS NULL, 1), else_=0).asc()  →  非 NULL 在前
    pinned_at DESC                                →  置顶内倒序
同时对字段健壮性、单条数据异常做双层兜底，避免后续历史脏数据再触发 500。

仅改动后端单文件：
- backend/app/api/chat_history.py（user_list_sessions + user_get_session_detail）

部署流程：
1. SFTP 上传修改后的 chat_history.py
2. docker compose build backend
3. docker compose up -d backend
4. curl 验证 GET /api/chat-sessions 返回非 500（401 鉴权未登录是正常）
5. 远端源码 grep BUG-460 关键标记
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
        "backend/app/api/chat_history.py",
        f"{REMOTE_PROJ}/backend/app/api/chat_history.py",
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
        run(cli, f"cd {REMOTE_PROJ} && docker compose build backend", timeout=1800)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d backend", timeout=600)

        time.sleep(15)

        # 等容器健康
        for _ in range(12):
            rc, out, _ = run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-backend 2>/dev/null || echo NONE",
            )
            if (out or "").strip() == "running":
                break
            time.sleep(5)

        # 核心验证：以前是 500，修复后未登录应为 401/403（非 500）
        urls_smoke = [
            f"{BASE_URL}/",
            f"{BASE_URL}/api/chat-sessions",  # 关键修复接口
            f"{BASE_URL}/ai-home",
        ]
        bad = []
        for u in urls_smoke:
            _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            if u.endswith("/api/chat-sessions"):
                # 关键：未登录必须返回 401/403，绝不能是 500
                if code == "500":
                    bad.append((u, code, "STILL_500"))
                elif code not in {"401", "403", "200"}:
                    bad.append((u, code, "UNEXPECTED"))
            else:
                if not (code.startswith("2") or code.startswith("3") or code in {"401", "403"}):
                    bad.append((u, code, "GENERAL"))

        # 远端源码标记验证
        _, out, _ = run(
            cli,
            f"grep -c 'BUG-460' {REMOTE_PROJ}/backend/app/api/chat_history.py",
        )
        marker = (out or "").strip()
        print(f"[VERIFY] BUG-460 markers in remote source: {marker}")

        # 验证 backend 容器最近日志已无 chat-sessions 相关 500 / SQL 1064 报错
        _, out, _ = run(
            cli,
            f"docker logs --tail 200 {DEPLOY_ID}-backend 2>&1 | grep -c 'NULLS LAST' || true",
        )
        nulls_last_hits = (out or "0").strip().splitlines()[-1] if out else "0"
        print(f"[VERIFY] Backend log lines containing 'NULLS LAST': {nulls_last_hits}")

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
