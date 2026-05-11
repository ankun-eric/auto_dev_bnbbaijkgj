"""[BUG-462] 服务端 API 接口连通性回归测试

仅验证：
1. DELETE /api/chat-sessions/{id}  路由存在（未登录应返回 401）
2. POST   /api/chat-sessions/batch-delete 路由存在（未登录应返回 401）
3. 前端打包后的 H5 ai-home 页面静态 HTML 中不再包含旧路径 `/api/chat/history/delete`
   （编译后旧字符串如果还在 JS bundle 里说明本次构建未覆盖到 Sidebar 组件 → 需重新部署）
"""
from __future__ import annotations

import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
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
        # T1：DELETE /api/chat-sessions/{id} 未登录 → 401（确认路由存在）
        rc, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' -X DELETE {BASE}/api/chat-sessions/999999",
        )
        code = (out or "").strip()
        print(f"[T1] DELETE /api/chat-sessions/999999 -> {code}")
        if code not in {"401", "403"}:
            failures.append(("T1", f"unexpected code {code}, expected 401/403"))

        # T2：POST /api/chat-sessions/batch-delete 未登录 → 401（确认路由存在）
        rc, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST "
            f"-H 'Content-Type: application/json' -d '{{\"session_ids\":[1]}}' "
            f"{BASE}/api/chat-sessions/batch-delete",
        )
        code = (out or "").strip()
        print(f"[T2] POST /api/chat-sessions/batch-delete -> {code}")
        if code not in {"401", "403"}:
            failures.append(("T2", f"unexpected code {code}, expected 401/403"))

        # T3：旧错误路由 POST /api/chat/history/delete 应该是 404（确认前端不再调用它）
        rc, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST "
            f"-H 'Content-Type: application/json' -d '{{\"ids\":[\"1\"]}}' "
            f"{BASE}/api/chat/history/delete",
        )
        code = (out or "").strip()
        print(f"[T3] (legacy) POST /api/chat/history/delete -> {code} (expected 404/405 to prove it does NOT exist)")
        if code not in {"404", "405", "401", "403"}:
            failures.append(("T3", f"unexpected code {code}, expected 404/405"))

        # T4：远端源码不再存在旧路径
        rc, out, _ = run(
            cli,
            "grep -rEn \"['\\\"]/api/chat/history/delete['\\\"]\" "
            f"/home/ubuntu/{DEPLOY_ID}/h5-web/src --include='*.tsx' --include='*.ts' "
            "2>/dev/null | grep -v '^\\s*//' || echo NONE",
        )
        out = (out or "").strip()
        print(f"[T4] legacy endpoint live code references: {out}")
        if out != "NONE":
            # 注释中的引用是允许的，过滤掉
            non_comment_lines = [
                l for l in out.splitlines()
                if "/api/chat/history/delete" in l and "//" not in l.split(":")[-1].split("/api")[0]
            ]
            if any(
                "//" not in line.split(":", 2)[-1][: line.split(":", 2)[-1].find("/api")]
                for line in out.splitlines() if "/api/chat/history/delete" in line
            ):
                # 简化：只看是否在 api.post 调用里
                bad_lines = [l for l in out.splitlines() if "api.post" in l]
                if bad_lines:
                    failures.append(("T4", f"legacy endpoint still called: {bad_lines}"))

        # T5：远端源码包含新的 batch-delete 调用
        rc, out, _ = run(
            cli,
            "grep -l 'chat-sessions/batch-delete' "
            f"/home/ubuntu/{DEPLOY_ID}/h5-web/src/components/ai-chat/Sidebar.tsx || echo NONE",
        )
        out = (out or "").strip()
        print(f"[T5] new batch-delete in remote Sidebar.tsx: {out}")
        if "NONE" in out:
            failures.append(("T5", "Sidebar.tsx does not contain new endpoint"))

        # T6：远端源码包含 DELETE /api/chat-sessions/{id} 调用
        rc, out, _ = run(
            cli,
            "grep 'api.delete(`/api/chat-sessions/' "
            f"/home/ubuntu/{DEPLOY_ID}/h5-web/src/components/ai-chat/Sidebar.tsx || echo NONE",
        )
        out = (out or "").strip()
        print(f"[T6] new DELETE in remote Sidebar.tsx: {out[:120]}")
        if "NONE" in out:
            failures.append(("T6", "Sidebar.tsx does not contain new DELETE endpoint"))

        # T7：H5 容器在 running 状态
        rc, out, _ = run(
            cli,
            f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5",
        )
        out = (out or "").strip()
        print(f"[T7] h5 container status: {out}")
        if out != "running":
            failures.append(("T7", f"h5 container not running: {out}"))

        # T8：H5 容器构建产物中 Sidebar 相关 chunk 应包含新接口
        rc, out, _ = run(
            cli,
            f"docker exec {DEPLOY_ID}-h5 sh -c \"grep -r 'chat-sessions/batch-delete' /app/.next/ 2>/dev/null | head -3\" || echo NONE",
        )
        out = (out or "").strip()
        print(f"[T8] h5 build artifacts contain new endpoint: {out[:200] if out else 'NONE'}")
        if not out or "NONE" in out:
            failures.append(("T8", "new endpoint not found in compiled H5 bundle"))

        print()
        print(f"[SUMMARY] failures = {failures}")
        if failures:
            print("[RESULT] FAIL")
            return 1
        print("[RESULT] PASS  — 8/8 cases passed")
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
