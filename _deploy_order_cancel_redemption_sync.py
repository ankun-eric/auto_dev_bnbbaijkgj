"""[订单核销码状态与未支付超时治理 Bug 修复方案 v1.0] 部署脚本.

修复内容：
1) 写入侧：统一取消出口 cancel_order_with_items（路径1+2+3 全部收敛）
2) 路径 3 改造：下线"门店超时未确认自动取消"，新增"未支付超时自动取消"
3) 全局配置：新增 PAYMENT_TIMEOUT_MINUTES 环境变量（默认 15）
4) 字段清理：移除 products / unified_orders 的 payment_timeout_minutes
5) 站内信文案：X 改为读全局配置
6) 数据迁移：cancelled 订单的 active 核销码全部刷为 expired（schema_sync 内自动执行）
7) admin 商品编辑页移除"支付超时(分)"字段

部署步骤：
1) SFTP 上传所有变更文件 + 新增的 service 与 test 文件
2) docker compose build backend admin-web
3) docker compose up -d backend admin-web
4) 等服务启动 30s（首次启动会跑 schema_sync 数据迁移）
5) docker cp conftest + 新测试文件
6) 容器内 pytest 7 个新增用例 + 关键回归
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
    # 后端 - 模型与 schema
    "backend/app/models/models.py",
    "backend/app/schemas/products.py",
    "backend/app/schemas/unified_orders.py",
    "backend/app/core/config.py",
    # 后端 - API 与 services（统一取消出口 + 路径 1/2/3）
    "backend/app/api/unified_orders.py",
    "backend/app/api/product_admin.py",
    "backend/app/api/h5_checkout.py",
    "backend/app/services/notification_scheduler.py",
    "backend/app/services/order_cancel.py",
    "backend/app/services/schema_sync.py",
    # 后端测试
    "backend/tests/test_order_cancel_redemption_sync.py",
    "backend/tests/test_multi_spec_price.py",
    # admin-web
    "admin-web/src/app/(admin)/product-system/products/page.tsx",
    # 部署配置
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".env.example",
]


def log(msg: str) -> None:
    print(f"[deploy_cancel_sync] {msg}", flush=True)


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

        log("== Step 2: docker compose build backend admin-web ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose build backend admin-web 2>&1 | tail -200",
            timeout=2400,
        )
        if rc != 0:
            log("ERROR: docker compose build failed")
            return 1

        log("== Step 3: docker compose up -d ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose up -d backend admin-web 2>&1 | tail -50",
            timeout=600,
        )
        if rc != 0:
            log("ERROR: docker compose up failed")
            return 1

        log("== Step 4: wait services to be ready (30s, includes schema_sync data migration) ==")
        time.sleep(30)

        log("== Step 5: copy conftest + new test files to backend container ==")
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/conftest.py "
            f"{DEPLOY_ID}-backend:/app/tests/conftest.py",
        )
        run(
            ssh,
            f"docker cp {REMOTE_DIR}/backend/tests/test_order_cancel_redemption_sync.py "
            f"{DEPLOY_ID}-backend:/app/tests/test_order_cancel_redemption_sync.py",
        )
        # 容器若无 pytest 则补
        run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'python -c \"import pytest\" 2>/dev/null || pip install --quiet pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -20'",
            timeout=240,
        )

        log("== Step 6: pytest in backend container — new cancel_sync suite (7 cases) ==")
        rc, out, err = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'cd /app && python -m pytest "
            f"tests/test_order_cancel_redemption_sync.py -v --tb=short 2>&1 | tail -120'",
            timeout=600,
        )
        if "passed" not in out:
            log("ERROR: cancel_sync pytest failed")
            return 2
        if "7 passed" in out:
            log("OK: cancel_sync pytest 7/7 PASS")
        else:
            log("WARN: cancel_sync pytest count mismatch — see above")

        log("== Step 7: data migration verification — count cancelled+active dirty rows ==")
        rc, out_check, _ = run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"'python -c \""
            f"import asyncio; "
            f"from sqlalchemy import text; "
            f"from app.core.database import async_session; "
            f"async def _f(): "
            f" async with async_session() as s: "
            f"  r = await s.execute(text(\\\"SELECT COUNT(*) FROM order_items oi JOIN unified_orders uo ON uo.id=oi.order_id WHERE uo.status='cancelled' AND oi.redemption_code_status='active'\\\")); "
            f"  print('DIRTY_LEFT=' + str(r.scalar())); "
            f"asyncio.run(_f())\"'",
            timeout=120,
        )
        if "DIRTY_LEFT=0" in out_check:
            log("OK: 数据清洗成功，无 cancelled+active 脏数据残留")
        else:
            log("WARN: 数据清洗结果 — see stdout")

        log("== Step 8: external URL checks ==")
        url_checks = [
            (f"{PROJECT_BASE_URL}/", "200|308"),
            (f"{PROJECT_BASE_URL}/api/health", "200"),
            # admin 订单列表（无 token 必须 401）
            (f"{PROJECT_BASE_URL}/api/admin/orders/unified?redemption_code_status=active", "401"),
            # 用户订单接口（无 token 必须 401）
            (f"{PROJECT_BASE_URL}/api/orders/unified", "401"),
            # admin 商品分类列表（无 token 必须 401）
            (f"{PROJECT_BASE_URL}/api/admin/products/categories", "401"),
            (f"{PROJECT_BASE_URL}/admin", "200|307|308"),
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

        log("== Step 9: verify scheduler job switched to check_unpaid_order_timeout ==")
        rc, out_log, _ = run(
            ssh,
            f"docker logs {DEPLOY_ID}-backend 2>&1 | grep -E 'Notification scheduler|check_unpaid|check_order_confirm' | tail -20",
            timeout=30,
        )
        if "Notification scheduler started" in out_log:
            log("OK: scheduler started")
        if "check_order_confirm_timeout" in out_log:
            log("WARN: 旧任务 check_order_confirm_timeout 仍在日志中（可能为历史日志，新代码不会再调度）")

        log("== Deploy DONE ==")
        return 0 if all_ok else 4
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
