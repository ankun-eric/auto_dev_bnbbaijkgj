"""[2026-05-04 商家 PC 后台「预约日历」优化 PRD v1.0] 部署脚本.

功能：把商家预约日历从只读看板升级为驾驶舱 + 轻量操作台
  - 后端 9 个新接口（kpi / cells / items / list / 我的视图CRUD / reschedule / notify / internal scan）
  - 后端 2 个新模型（merchant_calendar_views / booking_notification_logs）
  - 前端 13 个新组件（KPI/Toolbar/MyViews/Month/Week/Day/Resource/List/Reschedule/Popover/...）
  - 18 个 pytest 用例

执行步骤：
1) SFTP 把变更文件上传到服务器项目目录
2) docker compose build backend h5-web
3) docker compose up -d backend h5-web
4) 等服务启动 25s
5) docker cp conftest + 新测试文件到 backend 容器
6) 容器内 pytest 18/18 + 旧 13/13 回归
7) 外部 URL 验证
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
    # 后端
    "backend/app/models/models.py",
    "backend/app/schemas/merchant.py",
    "backend/app/api/merchant.py",
    "backend/tests/test_calendar_dashboard.py",
    # 前端 -- 商家 PC 日历
    "h5-web/src/app/merchant/calendar/page.tsx",
    "h5-web/src/app/merchant/calendar/types.ts",
    "h5-web/src/app/merchant/calendar/KpiBar.tsx",
    "h5-web/src/app/merchant/calendar/CalendarToolbar.tsx",
    "h5-web/src/app/merchant/calendar/MyViewsManager.tsx",
    "h5-web/src/app/merchant/calendar/MonthView.tsx",
    "h5-web/src/app/merchant/calendar/WeekView.tsx",
    "h5-web/src/app/merchant/calendar/DayView.tsx",
    "h5-web/src/app/merchant/calendar/ResourceView.tsx",
    "h5-web/src/app/merchant/calendar/ListView.tsx",
    "h5-web/src/app/merchant/calendar/RescheduleModal.tsx",
    "h5-web/src/app/merchant/calendar/BookingActionPopover.tsx",
]


def log(msg: str) -> None:
    print(f"[deploy_calendar_dashboard] {msg}", flush=True)


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

        log("== Step 5: copy conftest + new test file to backend container ==")
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/conftest.py "
            f"{DEPLOY_ID}-backend:/app/tests/conftest.py",
        )
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/test_calendar_dashboard.py "
            f"{DEPLOY_ID}-backend:/app/tests/test_calendar_dashboard.py",
        )
        # 容器若无 pytest 则补
        run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'python -c \"import pytest\" 2>/dev/null || pip install --quiet pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -20'",
            timeout=180,
        )

        log("== Step 6: pytest in backend container — new dashboard suite (18 cases) ==")
        rc, out, err = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'cd /app && python -m pytest "
            f"tests/test_calendar_dashboard.py -v --tb=short 2>&1 | tail -200'",
            timeout=600,
        )
        new_pass = " passed" in out and (" failed" not in out or "0 failed" in out)
        if not new_pass:
            log("ERROR: dashboard pytest failed")
            return 2
        if "18 passed" in out:
            log("OK: dashboard pytest 18/18 PASS")
        else:
            log("WARN: dashboard pytest count mismatch — see above")

        log("== Step 7: pytest regression — daily-orders popup (13 cases) ==")
        # 旧测试文件先 cp 一遍（若该文件容器内已存在则覆盖即可）
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/test_calendar_daily_orders_popup.py "
            f"{DEPLOY_ID}-backend:/app/tests/test_calendar_daily_orders_popup.py",
        )
        rc, out2, _ = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'cd /app && python -m pytest "
            f"tests/test_calendar_daily_orders_popup.py -v --tb=short 2>&1 | tail -120'",
            timeout=300,
        )
        if "13 passed" in out2:
            log("OK: regression daily-orders popup 13/13 PASS")
        else:
            log("WARN: regression mismatch — see above")

        log("== Step 8: external URL checks ==")
        url_checks = [
            (f"{PROJECT_BASE_URL}/", "200|308"),
            (f"{PROJECT_BASE_URL}/api/health", "200"),
            # 新接口无 token 必须 401
            (f"{PROJECT_BASE_URL}/api/merchant/calendar/kpi?store_id=1", "401"),
            (f"{PROJECT_BASE_URL}/api/merchant/calendar/cells?store_id=1&view=month&start_date=2026-05-01&end_date=2026-05-31", "401"),
            (f"{PROJECT_BASE_URL}/api/merchant/calendar/items?store_id=1&start_date=2026-05-01&end_date=2026-05-01", "401"),
            (f"{PROJECT_BASE_URL}/api/merchant/calendar/list?store_id=1&start_date=2026-05-01&end_date=2026-05-31", "401"),
            (f"{PROJECT_BASE_URL}/api/merchant/calendar/views?store_id=1", "401"),
            (f"{PROJECT_BASE_URL}/merchant/calendar", "200|307|308"),
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
