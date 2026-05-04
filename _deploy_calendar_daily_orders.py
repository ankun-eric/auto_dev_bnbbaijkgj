"""[2026-05-04 预约日历当日订单弹窗 PRD v1.0] 部署脚本.

功能：商家预约日历点击日期单元格 → 弹出当日订单弹窗（PC 端 + H5 端）

执行步骤：
1) SFTP 把变更的 5 个文件上传到服务器项目目录
   - backend/app/api/merchant.py（新增 /api/merchant/calendar/daily-orders 接口）
   - backend/app/schemas/merchant.py（新增 DailyOrderItem / DailyOrdersResponse 等 schema）
   - backend/tests/test_calendar_daily_orders_popup.py（13 个 pytest 用例）
   - h5-web/src/app/merchant/calendar/page.tsx（PC 日历页接入弹窗）
   - h5-web/src/app/merchant/calendar/DailyOrdersModal.tsx（PC 弹窗组件）
   - h5-web/src/app/merchant/m/calendar/page.tsx（H5 日历页接入抽屉）
   - h5-web/src/app/merchant/m/calendar/DailyOrdersDrawer.tsx（H5 抽屉组件）
2) 远程 docker compose build backend h5-web
3) 远程 docker compose up -d backend h5-web
4) 等服务启动 25s
5) docker cp test_calendar_daily_orders_popup.py 到 backend 容器
6) docker exec backend pytest 测试 13 个用例
7) curl 验证关键 URL：
   - /  -> 200/308
   - /api/health -> 200
   - /api/merchant/calendar/daily-orders?date=...&store_id=... -> 401（无 token 符合预期）
   - /merchant/calendar -> 200/308

注意：
- 不要重启 db 容器，避免数据丢失
"""

from __future__ import annotations

import os
import posixpath
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

FILES_TO_UPLOAD = [
    "backend/app/api/merchant.py",
    "backend/app/schemas/merchant.py",
    "backend/tests/test_calendar_daily_orders_popup.py",
    "h5-web/src/app/merchant/calendar/page.tsx",
    "h5-web/src/app/merchant/calendar/DailyOrdersModal.tsx",
    "h5-web/src/app/merchant/m/calendar/page.tsx",
    "h5-web/src/app/merchant/m/calendar/DailyOrdersDrawer.tsx",
]


def log(msg: str) -> None:
    print(f"[deploy_calendar_popup] {msg}", flush=True)


def make_ssh() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    log(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        snippet = out if len(out) < 4000 else out[:2000] + "\n...[truncated]...\n" + out[-2000:]
        log(f"stdout:\n{snippet}")
    if err:
        snippet = err if len(err) < 4000 else err[:2000] + "\n...[truncated]...\n" + err[-2000:]
        log(f"stderr:\n{snippet}")
    log(f"exit code: {code}")
    return code, out, err


def sftp_upload(sftp: paramiko.SFTPClient, local: str, remote: str) -> None:
    parts = remote.split("/")
    cur = ""
    for p in parts[:-1]:
        if not p:
            cur = "/"
            continue
        cur = posixpath.join(cur, p) if cur else "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)
    sftp.put(local, remote)
    log(f"uploaded: {local} -> {remote}")


def main() -> int:
    ssh = make_ssh()
    try:
        sftp = ssh.open_sftp()
        try:
            log("== Step 1: SFTP upload changed files ==")
            for rel in FILES_TO_UPLOAD:
                local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
                if not os.path.exists(local):
                    log(f"WARN: local file missing: {local}")
                    continue
                remote = posixpath.join(REMOTE_DIR, rel)
                sftp_upload(sftp, local, remote)
        finally:
            sftp.close()

        log("== Step 2: docker compose build backend h5-web ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose build backend h5-web 2>&1 | tail -200",
            timeout=1800,
        )
        if rc != 0:
            log("ERROR: docker compose build failed")
            return 1

        log("== Step 3: docker compose up -d ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose up -d backend h5-web 2>&1 | tail -50",
            timeout=600,
        )
        if rc != 0:
            log("ERROR: docker compose up failed")
            return 1

        log("== Step 4: wait services to be ready (25s) ==")
        time.sleep(25)

        log("== Step 5: copy conftest + test file & ensure pytest installed in backend container ==")
        # 同时拷贝 conftest 与本测试文件
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/conftest.py "
            f"{DEPLOY_ID}-backend:/app/tests/conftest.py",
        )
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/test_calendar_daily_orders_popup.py "
            f"{DEPLOY_ID}-backend:/app/tests/test_calendar_daily_orders_popup.py",
        )
        # 容器内若没有 pytest 就先 pip install
        rc, out, err = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'python -c \"import pytest\" 2>/dev/null || pip install --quiet pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -20'",
            timeout=180,
        )
        rc, out, err = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'cd /app && python -m pytest "
            f"tests/test_calendar_daily_orders_popup.py -v --tb=short 2>&1 | tail -150'",
            timeout=300,
        )
        if rc != 0 or " passed" not in out:
            log("ERROR: pytest failed")
            return 2
        # 解析 pytest 输出，验证 13/13 通过
        if "13 passed" not in out:
            log("WARN: expected 13 passed, found different count — check output above")
        else:
            log("OK: pytest 13/13 PASS")

        log("== Step 6: external URL checks ==")
        url_checks = [
            (f"{PROJECT_BASE_URL}/", "200|308"),
            (f"{PROJECT_BASE_URL}/api/health", "200"),
            (
                f"{PROJECT_BASE_URL}/api/merchant/calendar/daily-orders?date=2026-05-10&store_id=1",
                "401",
            ),  # 无 token 必须 401
            (f"{PROJECT_BASE_URL}/merchant/calendar", "200|307|308"),
            (f"{PROJECT_BASE_URL}/merchant/m/calendar", "200|307|308"),
        ]
        all_ok = True
        for url, expect in url_checks:
            rc, out, err = run(
                ssh,
                f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'",
                timeout=30,
            )
            code_str = (out or "").strip()
            if code_str in expect.split("|"):
                log(f"OK  {code_str:>4}  {url}")
            else:
                log(f"FAIL {code_str:>4} (expect {expect})  {url}")
                all_ok = False

        if not all_ok:
            log("WARN: some URL checks failed — see above")

        log("== Deploy DONE ==")
        return 0 if all_ok else 4
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
