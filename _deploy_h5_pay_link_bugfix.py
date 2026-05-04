#!/usr/bin/env python3
"""[H5 支付链路 Bug 修复] 增量部署 + 容器内 pytest

修复内容：
- 后端：新增 confirm-free / sandbox-confirm 端点；pay 接口增加 pay_url 字段；新增历史数据校准脚本
- H5：动态拉取 available-methods + 0 元订单分支 + sandbox-pay 沙盒收银台页
- 小程序：动态支付方式 + confirm-free + 详情页 payOrder 改造
- Flutter：新增 getAvailablePayMethods / confirmFreeUnifiedOrder + checkout/订单详情/列表三处调用改造
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
    # 后端
    ("backend/app/api/unified_orders.py", "backend/app/api/unified_orders.py"),
    ("backend/app/schemas/unified_orders.py", "backend/app/schemas/unified_orders.py"),
    ("backend/app/core/config.py", "backend/app/core/config.py"),
    ("backend/scripts/fix_paid_orders_without_paid_at.py",
     "backend/scripts/fix_paid_orders_without_paid_at.py"),
    ("backend/tests/test_h5_pay_link_bugfix.py",
     "backend/tests/test_h5_pay_link_bugfix.py"),
    # H5
    ("h5-web/src/app/checkout/page.tsx", "h5-web/src/app/checkout/page.tsx"),
    ("h5-web/src/app/unified-order/[id]/page.tsx",
     "h5-web/src/app/unified-order/[id]/page.tsx"),
    ("h5-web/src/app/sandbox-pay/page.tsx",
     "h5-web/src/app/sandbox-pay/page.tsx"),
    # 小程序
    ("miniprogram/pages/checkout/index.js", "miniprogram/pages/checkout/index.js"),
    ("miniprogram/pages/checkout/index.wxml", "miniprogram/pages/checkout/index.wxml"),
    ("miniprogram/pages/checkout/index.wxss", "miniprogram/pages/checkout/index.wxss"),
    ("miniprogram/pages/unified-order-detail/index.js",
     "miniprogram/pages/unified-order-detail/index.js"),
    # Flutter
    ("flutter_app/lib/config/api_config.dart", "flutter_app/lib/config/api_config.dart"),
    ("flutter_app/lib/services/api_service.dart", "flutter_app/lib/services/api_service.dart"),
    ("flutter_app/lib/screens/product/checkout_screen.dart",
     "flutter_app/lib/screens/product/checkout_screen.dart"),
    ("flutter_app/lib/screens/order/unified_order_detail_screen.dart",
     "flutter_app/lib/screens/order/unified_order_detail_screen.dart"),
    ("flutter_app/lib/screens/order/unified_orders_screen.dart",
     "flutter_app/lib/screens/order/unified_orders_screen.dart"),
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
        print(out[-3500:])
    if err:
        print("STDERR:", err[-1500:])
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

    print("\n=== Step 2: rebuild backend & h5-web containers ===")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose build backend h5-web 2>&1 | tail -40",
        timeout=2400,
    )
    if rc != 0:
        print("!! docker compose build 失败")
        sys.exit(3)

    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose up -d backend h5-web 2>&1 | tail -20",
        timeout=600,
    )
    if rc != 0:
        print("!! docker compose up 失败")
        sys.exit(4)

    print("\n=== Step 3: wait & container status ===")
    time.sleep(15)
    run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 4: pytest in backend container ===")
    backend_container = f"{DEPLOY_ID}-backend"
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_h5_pay_link_bugfix.py "
          f"{backend_container}:/app/tests/test_h5_pay_link_bugfix.py")

    run(c, f"docker exec {backend_container} pip install --no-cache-dir "
          f"pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -8",
        timeout=300)

    rc, out, _ = run(
        c,
        f"docker exec -e PYTHONPATH=/app {backend_container} "
        f"python -m pytest tests/test_h5_pay_link_bugfix.py "
        f"tests/test_coupon_usable_for_order.py "
        f"tests/test_checkout_date_mode_no_time_slot.py "
        f"-v --tb=short 2>&1 | tail -80",
        timeout=600,
    )

    print("\n=== Step 5: verify external URLs ===")
    base = "https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID
    for path in ["/", "/admin/", "/api/health", "/sandbox-pay/?order_no=demo&channel=alipay_h5"]:
        run(c, f"curl -s -o /dev/null -w 'GET {path} → %{{http_code}}\\n' '{base}{path}'")

    sftp.close()
    c.close()
    print("\n=== Deploy & test done ===")


if __name__ == "__main__":
    main()
