#!/usr/bin/env python3
"""[2026-05-04 核销订单过期+改期规则优化 v1.0] 增量部署 + 容器内 pytest

变更范围（后端）：
- backend/app/models/models.py：Product.allow_reschedule, UnifiedOrder.reschedule_count/limit
- backend/app/services/schema_sync.py：新增 _sync_reschedule_columns
- backend/app/schemas/products.py / unified_orders.py：补字段
- backend/app/api/product_admin.py / unified_orders.py：写入 + 响应
- backend/app/api/stores_public.py：新增「联系商家」公共门店信息接口
- backend/app/main.py：注册 stores_public 路由
- backend/app/tasks/order_status_auto_progress.py：错过预约规则重构（替代 R2）
- backend/tests/test_reschedule_overdue_rules.py：16 用例回归
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
    # backend
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/services/schema_sync.py", "backend/app/services/schema_sync.py"),
    ("backend/app/schemas/products.py", "backend/app/schemas/products.py"),
    ("backend/app/schemas/unified_orders.py", "backend/app/schemas/unified_orders.py"),
    ("backend/app/api/product_admin.py", "backend/app/api/product_admin.py"),
    ("backend/app/api/unified_orders.py", "backend/app/api/unified_orders.py"),
    ("backend/app/api/stores_public.py", "backend/app/api/stores_public.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/app/tasks/order_status_auto_progress.py",
     "backend/app/tasks/order_status_auto_progress.py"),
    ("backend/tests/test_reschedule_overdue_rules.py",
     "backend/tests/test_reschedule_overdue_rules.py"),
    # admin-web
    ("admin-web/src/app/(admin)/product-system/products/page.tsx",
     "admin-web/src/app/(admin)/product-system/products/page.tsx"),
    # h5-web
    ("h5-web/src/app/orders/components/ContactStoreModal.tsx",
     "h5-web/src/app/orders/components/ContactStoreModal.tsx"),
    ("h5-web/src/app/unified-orders/page.tsx",
     "h5-web/src/app/unified-orders/page.tsx"),
    ("h5-web/src/app/unified-order/[id]/page.tsx",
     "h5-web/src/app/unified-order/[id]/page.tsx"),
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

    print("\n=== Step 2: rebuild backend + admin-web + h5-web ===")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose build backend admin-web h5-web 2>&1 | tail -60",
        timeout=2400,
    )
    if rc != 0:
        print("!! docker compose build 失败")
        sys.exit(3)

    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose up -d 2>&1 | tail -30",
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
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_reschedule_overdue_rules.py "
          f"{backend_container}:/app/tests/test_reschedule_overdue_rules.py")

    run(c, f"docker exec {backend_container} pip install --no-cache-dir "
          f"pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -6",
        timeout=300)

    print("\n=== Step 5: pytest 16 用例 ===")
    rc, out, _ = run(
        c,
        f"docker exec -e PYTHONPATH=/app {backend_container} "
        f"python -m pytest tests/test_reschedule_overdue_rules.py "
        f"-v --tb=short 2>&1 | tail -200",
        timeout=900,
    )

    print("\n=== Step 6: verify DB schema 新字段 ===")
    db_container = f"{DEPLOY_ID}-mysql"
    for col_q in [
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_NAME='products' AND COLUMN_NAME='allow_reschedule'",
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_NAME='unified_orders' AND COLUMN_NAME='reschedule_count'",
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_NAME='unified_orders' AND COLUMN_NAME='reschedule_limit'",
    ]:
        run(c, f"docker exec {db_container} sh -lc \"mysql -uroot -proot bini_health -e "
              f"\\\"{col_q}\\\"\" 2>&1 | tail -5")

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
