"""[BUG-466 (2026-05-11)] 部署脚本 — AI 对话首页「自动新会话切片」失效修复

修复范围（前后端联调）：
  后端：
    - backend/app/api/chat_history.py：
        a) 新增 POST /api/chat-sessions/{session_id}/archive（强一致归档接口）
        b) POST /api/chat-sessions 新增可选字段 archive_previous_session_id
    - backend/app/schemas/chat_history.py：UserChatSessionCreate 新增 archive_previous_session_id
  前端：
    - h5-web/src/app/(ai-chat)/ai-home/page.tsx：
        a) 引入 currentSidRef，所有 setSessionId 配套写入；闭包旧 sid 问题彻底规避
        b) handleConsultantSelect 调合并接口（归档+创建），并派发 bh-history-refresh
        c) 6 小时自动切片改为统一 runActiveCheck，挂载/visibilitychange/focus/pageshow
           四时机全部触发；发送前 checkIdleAndMaybeNewSession 做最后兜底
        d) handleSelectSession / handleNewConversation / handleUndoSwitch 配套同步更新 ref

部署流程：
  1. SFTP 上传 4 个文件
  2. docker compose build backend h5-web
  3. docker compose up -d backend h5-web
  4. 等容器健康，curl 验证关键路由 + 关键源码标记
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
    (
        "backend/app/schemas/chat_history.py",
        f"{REMOTE_PROJ}/backend/app/schemas/chat_history.py",
    ),
    (
        "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        f"{REMOTE_PROJ}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
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

        # ─── 源码标记校验 ───
        # 后端：BUG-466 标记 + archive 接口存在
        _, out, _ = run(
            cli,
            f"grep -c 'BUG-466' {REMOTE_PROJ}/backend/app/api/chat_history.py",
        )
        print(f"[VERIFY] backend BUG-466 markers: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'archive_previous_session_id' {REMOTE_PROJ}/backend/app/api/chat_history.py",
        )
        print(f"[VERIFY] backend archive_previous_session_id occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c '/archive' {REMOTE_PROJ}/backend/app/api/chat_history.py",
        )
        print(f"[VERIFY] backend /archive route occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'archive_previous_session_id' {REMOTE_PROJ}/backend/app/schemas/chat_history.py",
        )
        print(f"[VERIFY] schema archive_previous_session_id occurrences: {(out or '').strip()}")

        # 前端：BUG-466 标记 + currentSidRef + runActiveCheck + bh-history-refresh
        _, out, _ = run(
            cli,
            f"grep -c 'BUG-466' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] frontend BUG-466 markers: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'currentSidRef' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] frontend currentSidRef occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'runActiveCheck' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] frontend runActiveCheck occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'bh-history-refresh' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] frontend bh-history-refresh occurrences: {(out or '').strip()}")

        # ─── 构建并启动容器 ───
        # 后端镜像构建
        run(cli, f"cd {REMOTE_PROJ} && docker compose build backend", timeout=2400)
        # 前端镜像构建（耗时较长）
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=3600)
        # 重启
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d backend h5-web", timeout=600)

        time.sleep(15)

        # 等待两个容器健康
        for _ in range(36):
            _, out_b, _ = run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-backend 2>/dev/null || echo NONE",
            )
            _, out_h, _ = run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5 2>/dev/null || echo NONE",
            )
            if (out_b or "").strip() == "running" and (out_h or "").strip() == "running":
                break
            time.sleep(5)

        # ─── smoke：关键路由可达性 ───
        bad: list[tuple[str, str, str]] = []
        # T1: 前端 ai-home 页面应可达（200/302/3xx）
        _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/ai-home")
        code = (out or "").strip()
        print(f"[SMOKE T1] /ai-home -> {code}")
        if not (code.startswith("2") or code.startswith("3")):
            bad.append(("/ai-home", code, "FE_UNREACHABLE"))

        # T2: 后端 GET /api/chat-sessions 未登录应 401（非 500）
        _, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/chat-sessions",
        )
        code = (out or "").strip()
        print(f"[SMOKE T2] GET /api/chat-sessions -> {code}")
        if code in {"500"}:
            bad.append(("/api/chat-sessions", code, "BACKEND_500"))
        elif code not in {"401", "403", "200"}:
            bad.append(("/api/chat-sessions", code, "UNEXPECTED"))

        # T3: 后端 POST /api/chat-sessions 未登录应 401（非 404；证明合并接口已注册）
        _, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"session_type\":\"health_qa\",\"archive_previous_session_id\":1}}' "
            f"{BASE_URL}/api/chat-sessions",
        )
        code = (out or "").strip()
        print(f"[SMOKE T3] POST /api/chat-sessions (with archive_previous_session_id) -> {code}")
        if code == "404":
            bad.append(("POST /api/chat-sessions", code, "NOT_FOUND"))
        elif code == "500":
            bad.append(("POST /api/chat-sessions", code, "BACKEND_500"))
        elif code not in {"401", "403", "422", "400", "200"}:
            bad.append(("POST /api/chat-sessions", code, "UNEXPECTED"))

        # T4: 新增 POST /api/chat-sessions/{id}/archive 未登录应 401（非 404；证明 archive 接口已注册）
        _, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST "
            f"{BASE_URL}/api/chat-sessions/999999/archive",
        )
        code = (out or "").strip()
        print(f"[SMOKE T4] POST /api/chat-sessions/999999/archive -> {code}")
        if code == "404":
            # 404 是路由没注册（不是 session 不存在 404，后者要 401 通过之后）
            # 注意：FastAPI 在没认证时会先返回 401，所以这里 404 表示路由没注册
            bad.append(("POST /api/chat-sessions/{id}/archive", code, "ROUTE_NOT_FOUND"))
        elif code == "500":
            bad.append(("POST /api/chat-sessions/{id}/archive", code, "BACKEND_500"))
        elif code not in {"401", "403", "405", "200"}:
            bad.append(("POST /api/chat-sessions/{id}/archive", code, "UNEXPECTED"))

        # T5: GET /api/chat-sessions/active-check 未登录应 401（非 500）
        _, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/chat-sessions/active-check",
        )
        code = (out or "").strip()
        print(f"[SMOKE T5] GET /api/chat-sessions/active-check -> {code}")
        if code == "500":
            bad.append(("/api/chat-sessions/active-check", code, "BACKEND_500"))
        elif code not in {"401", "403", "200"}:
            bad.append(("/api/chat-sessions/active-check", code, "UNEXPECTED"))

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
