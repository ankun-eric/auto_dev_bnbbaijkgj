#!/usr/bin/env python3
"""[优惠券下单页 Bug 修复 v2] 增量部署 + 容器内 pytest

修复 4 个 Bug：
- B1: 免费试用券 0 元抵扣
- B2: 后台 free_trial 隐藏门槛/优惠金额字段
- B3: 下单页券列表过滤（新增 /api/coupons/usable-for-order + 创单兜底）
- B4: 圆圈对齐（H5/小程序/Flutter）

策略：
1. SFTP 上传本次改动的后端、admin-web、h5-web、miniprogram、flutter 文件到服务器
2. 在服务器上 docker compose build + up backend + admin-web + h5-web
3. 在 backend 容器内安装 pytest 并运行新增/回归测试
4. 验证基础访问
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

# 本次改动的文件清单
FILES = [
    # 后端
    ("backend/app/api/coupons.py", "backend/app/api/coupons.py"),
    ("backend/app/api/unified_orders.py", "backend/app/api/unified_orders.py"),
    ("backend/tests/test_coupon_usable_for_order.py",
     "backend/tests/test_coupon_usable_for_order.py"),
    # admin-web
    ("admin-web/src/app/(admin)/product-system/coupons/page.tsx",
     "admin-web/src/app/(admin)/product-system/coupons/page.tsx"),
    # H5
    ("h5-web/src/app/checkout/page.tsx", "h5-web/src/app/checkout/page.tsx"),
    # 小程序（源码部署）
    ("miniprogram/pages/checkout/index.js", "miniprogram/pages/checkout/index.js"),
    ("miniprogram/pages/checkout/index.wxml", "miniprogram/pages/checkout/index.wxml"),
    ("miniprogram/pages/checkout/index.wxss", "miniprogram/pages/checkout/index.wxss"),
    # Flutter
    ("flutter_app/lib/config/api_config.dart", "flutter_app/lib/config/api_config.dart"),
    ("flutter_app/lib/services/api_service.dart", "flutter_app/lib/services/api_service.dart"),
    ("flutter_app/lib/models/coupon.dart", "flutter_app/lib/models/coupon.dart"),
    ("flutter_app/lib/screens/product/checkout_screen.dart",
     "flutter_app/lib/screens/product/checkout_screen.dart"),
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
        print(out[-3000:])
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

    print("\n=== Step 2: rebuild backend & admin-web & h5-web containers ===")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose build backend admin-web h5-web 2>&1 | tail -40",
        timeout=2400,
    )
    if rc != 0:
        print("!! docker compose build 失败")
        sys.exit(3)

    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose up -d backend admin-web h5-web 2>&1 | tail -20",
        timeout=600,
    )
    if rc != 0:
        print("!! docker compose up 失败")
        sys.exit(4)

    print("\n=== Step 3: wait & check container status ===")
    time.sleep(15)
    run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 4: install pytest deps & run tests in backend container ===")
    backend_container = f"{DEPLOY_ID}-backend"
    # 复制测试文件到容器（保险）
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_coupon_usable_for_order.py "
          f"{backend_container}:/app/tests/test_coupon_usable_for_order.py")

    # 安装 pytest 依赖
    run(c, f"docker exec {backend_container} pip install --no-cache-dir "
          f"pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -10",
        timeout=300)

    # 运行本次新增 + 回归测试
    rc, out, _ = run(
        c,
        f"docker exec -e PYTHONPATH=/app {backend_container} "
        f"python -m pytest tests/test_coupon_usable_for_order.py "
        f"tests/test_checkout_date_mode_no_time_slot.py "
        f"-v --tb=short 2>&1 | tail -80",
        timeout=600,
    )

    print("\n=== Step 5: verify external URLs ===")
    base = "https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID
    for path in ["/", "/admin/", "/api/health"]:
        run(c, f"curl -s -o /dev/null -w 'GET {path} → %{{http_code}}\\n' {base}{path}")

    sftp.close()
    c.close()
    print("\n=== Deploy & test done ===")


if __name__ == "__main__":
    main()
