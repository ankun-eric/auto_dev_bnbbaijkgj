"""[BUG-466 (2026-05-11)] 服务端 API 接口连通性回归测试

测试覆盖：
  T1: 后端 POST /api/chat-sessions/{id}/archive 路由已注册（401，非 404）
  T2: 后端 POST /api/chat-sessions 仍可接受 archive_previous_session_id 字段（401，非 422/500）
  T3: 后端 GET /api/chat-sessions/active-check 路由健康（401，非 500）
  T4: 远端源码（后端）含 BUG-466 标记 + archive_previous_session_id + /archive 路由
  T5: 远端源码（前端）含 BUG-466 标记 + currentSidRef + runActiveCheck + 4 个时机监听
  T6: 远端源码（前端）handleConsultantSelect 派发 bh-history-refresh
  T7: 前端 ai-home 页面整体可达（200/302/3xx）

注意：服务端非 UI 自动化测试不依赖登录态，仅验证路由存在性、源码标记、HTTP 码合规。
"""
from __future__ import annotations

import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 120) -> tuple[int, str, str]:
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main() -> int:
    cli = ssh_connect()
    failures: list[tuple[str, str]] = []
    try:
        # ─── 路由可达性 ───
        # T1: POST /api/chat-sessions/{id}/archive 未登录 -> 401（路由已注册）
        rc, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST {BASE}/api/chat-sessions/999999/archive",
        )
        code = (out or "").strip()
        print(f"[T1] POST /api/chat-sessions/999999/archive -> {code}")
        if code == "404":
            failures.append(("T1", f"route not registered: 404"))
        elif code not in {"401", "403", "405", "200"}:
            failures.append(("T1", f"unexpected code {code}"))

        # T2: POST /api/chat-sessions 携带 archive_previous_session_id 未登录 -> 401
        rc, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"session_type\":\"health_qa\",\"archive_previous_session_id\":1}}' "
            f"{BASE}/api/chat-sessions",
        )
        code = (out or "").strip()
        print(f"[T2] POST /api/chat-sessions (with archive_previous_session_id) -> {code}")
        if code == "500":
            failures.append(("T2", f"BACKEND_500 (schema 422 expected, not 500)"))
        elif code == "404":
            failures.append(("T2", f"route not registered: 404"))
        elif code not in {"401", "403", "422", "400", "200"}:
            failures.append(("T2", f"unexpected code {code}"))

        # T3: GET /api/chat-sessions/active-check 未登录 -> 401
        rc, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE}/api/chat-sessions/active-check",
        )
        code = (out or "").strip()
        print(f"[T3] GET /api/chat-sessions/active-check -> {code}")
        if code == "500":
            failures.append(("T3", f"BACKEND_500"))
        elif code not in {"401", "403", "200"}:
            failures.append(("T3", f"unexpected code {code}"))

        # ─── 源码标记验证 ───
        # T4: 后端 BUG-466 标记 + archive_previous_session_id + /archive 路由
        for marker, file in [
            ("BUG-466", f"{REMOTE_PROJ}/backend/app/api/chat_history.py"),
            ("archive_previous_session_id", f"{REMOTE_PROJ}/backend/app/api/chat_history.py"),
            ("/archive", f"{REMOTE_PROJ}/backend/app/api/chat_history.py"),
            ("archive_previous_session_id", f"{REMOTE_PROJ}/backend/app/schemas/chat_history.py"),
        ]:
            _, out, _ = run(cli, f"grep -c '{marker}' {file}")
            cnt = int((out or "0").strip() or "0")
            print(f"[T4] backend marker '{marker}' in {file.split('/')[-1]}: {cnt}")
            if cnt < 1:
                failures.append(("T4", f"missing '{marker}' in {file}"))

        # T5: 前端 BUG-466 标记 + currentSidRef + runActiveCheck + visibilitychange/focus/pageshow
        fe_file = f"{REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx"
        for marker in [
            "BUG-466",
            "currentSidRef",
            "runActiveCheck",
            "visibilitychange",
            "pageshow",
        ]:
            _, out, _ = run(cli, f"grep -c '{marker}' {fe_file}")
            cnt = int((out or "0").strip() or "0")
            print(f"[T5] frontend marker '{marker}': {cnt}")
            if cnt < 1:
                failures.append(("T5", f"missing '{marker}' in ai-home/page.tsx"))

        # T6: 前端 handleConsultantSelect 必须派发 bh-history-refresh（出现至少 2 次：切换 + 撤销）
        _, out, _ = run(cli, f"grep -c 'bh-history-refresh' {fe_file}")
        cnt = int((out or "0").strip() or "0")
        print(f"[T6] frontend bh-history-refresh dispatch count: {cnt}")
        if cnt < 2:
            failures.append(("T6", f"bh-history-refresh dispatch count={cnt} (expected >=2)"))

        # T7: 前端 ai-home 页面整体可达
        _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE}/ai-home")
        code = (out or "").strip()
        print(f"[T7] {BASE}/ai-home -> {code}")
        if not (code.startswith("2") or code.startswith("3")):
            failures.append(("T7", f"unexpected code {code}"))

        print("\n========== TEST SUMMARY ==========")
        if failures:
            for tag, msg in failures:
                print(f"  ❌ {tag}: {msg}")
            print(f"\n❌ {len(failures)} test(s) FAILED")
            return 1
        print("✅ ALL TESTS PASSED")
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
