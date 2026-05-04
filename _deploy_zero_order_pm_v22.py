#!/usr/bin/env python3
"""[2026-05-04 零元单支付方式标记 v2.2] 增量部署 + 容器内 pytest

修复内容：
- backend/app/models/models.py:UnifiedPaymentMethod 新增 coupon_deduction
- backend/app/api/unified_orders.py:confirm_free_unified_order 写 payment_method
- backend/app/services/schema_sync.py:_sync_payment_config 末尾追加 ENUM 扩列
- backend/tests/test_zero_order_payment_method_v22.py: 4 用例回归
"""
import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/api/unified_orders.py", "backend/app/api/unified_orders.py"),
    ("backend/app/services/schema_sync.py", "backend/app/services/schema_sync.py"),
    ("backend/tests/test_zero_order_payment_method_v22.py",
     "backend/tests/test_zero_order_payment_method_v22.py"),
]


def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    return c


def run(c, cmd, timeout=900):
    print(f"\n>>> {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-5000:])
    if err:
        print("STDERR:", err[-2000:])
    print(f"--- EXIT {rc} ---")
    return rc, out, err


def upload(sftp, local, remote):
    parts = remote.split("/")
    d = ""
    for p in parts[:-1]:
        if not p:
            continue
        d = d + "/" + p
        try:
            sftp.stat(d)
        except IOError:
            try:
                sftp.mkdir(d)
            except IOError:
                pass
    print(f"  upload: {local}  ->  {remote}")
    sftp.put(local, remote)


def main():
    c = make_ssh()
    sftp = c.open_sftp()

    print("=== Step 1: upload changed files ===")
    for local_rel, remote_rel in FILES:
        local_abs = os.path.abspath(local_rel)
        remote_abs = f"{REMOTE_ROOT}/{remote_rel}"
        if not os.path.exists(local_abs):
            print(f"!! 缺失本地文件: {local_abs}")
            sys.exit(2)
        upload(sftp, local_abs, remote_abs)

    print("\n=== Step 2: rebuild backend container ===")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose build backend 2>&1 | tail -40",
        timeout=2400,
    )
    if rc != 0:
        print("!! docker compose build 失败")
        sys.exit(3)

    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose up -d backend 2>&1 | tail -20",
        timeout=600,
    )
    if rc != 0:
        print("!! docker compose up 失败")
        sys.exit(4)

    print("\n=== Step 3: wait & container status ===")
    time.sleep(25)
    run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 4: copy tests + conftest into backend container ===")
    backend_container = f"{DEPLOY_ID}-backend"
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/conftest.py "
          f"{backend_container}:/app/tests/conftest.py")
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_zero_order_payment_method_v22.py "
          f"{backend_container}:/app/tests/test_zero_order_payment_method_v22.py")
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_h5_pay_link_bugfix.py "
          f"{backend_container}:/app/tests/test_h5_pay_link_bugfix.py")

    run(c, f"docker exec {backend_container} pip install --no-cache-dir "
          f"pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -6",
        timeout=300)

    print("\n=== Step 5: pytest 新用例 4 + 旧用例 8 ===")
    rc, out, _ = run(
        c,
        f"docker exec -e PYTHONPATH=/app {backend_container} "
        f"python -m pytest tests/test_zero_order_payment_method_v22.py "
        f"tests/test_h5_pay_link_bugfix.py "
        f"-v --tb=short 2>&1 | tail -150",
        timeout=900,
    )

    print("\n=== Step 6: verify DB schema ENUM extension ===")
    db_container = f"{DEPLOY_ID}-mysql"
    run(c, f"docker exec {db_container} sh -lc \"mysql -uroot -proot bini_health -e "
          f"\\\"SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
          f"WHERE TABLE_NAME='unified_orders' AND COLUMN_NAME='payment_method'\\\"\" 2>&1 | tail -5")

    print("\n=== Step 7: verify external URLs ===")
    base = "https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID
    for path in ["/", "/admin/", "/api/health"]:
        run(c, f"curl -s -o /dev/null -w 'GET {path} -> %{{http_code}}\\n' '{base}{path}'")

    sftp.close()
    c.close()
    print("\n=== Deploy & test done ===")
    return rc


if __name__ == "__main__":
    sys.exit(main())
