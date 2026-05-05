#!/usr/bin/env python3
"""[2026-05-05 营业管理入口收敛 PRD v1.0] 部署脚本

策略：通过 SCP 上传本次涉及的源码文件 → 容器内 docker compose build --no-cache → up → 验证。
（绕过 GitHub fetch 不稳定）
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"
BACKEND_NAME = f"{PROJECT_ID}-backend"
ADMIN_NAME = f"{PROJECT_ID}-admin-web"
H5_NAME = f"{PROJECT_ID}-h5"

LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

FILES_TO_UPLOAD: list[tuple[str, str]] = [
    # 后端
    ("backend/app/models/models.py", f"{PROJECT_DIR}/backend/app/models/models.py"),
    ("backend/app/main.py", f"{PROJECT_DIR}/backend/app/main.py"),
    ("backend/app/api/order_enhancement.py", f"{PROJECT_DIR}/backend/app/api/order_enhancement.py"),
    ("backend/app/api/h5_checkout.py", f"{PROJECT_DIR}/backend/app/api/h5_checkout.py"),
    ("backend/app/api/product_admin.py", f"{PROJECT_DIR}/backend/app/api/product_admin.py"),
    ("backend/app/schemas/order_enhancement.py", f"{PROJECT_DIR}/backend/app/schemas/order_enhancement.py"),
    ("backend/app/schemas/products.py", f"{PROJECT_DIR}/backend/app/schemas/products.py"),
    ("backend/tests/test_business_config_unify_v1.py", f"{PROJECT_DIR}/backend/tests/test_business_config_unify_v1.py"),
    ("backend/tests/test_order_enhancement.py", f"{PROJECT_DIR}/backend/tests/test_order_enhancement.py"),
    # admin-web
    ("admin-web/src/app/(admin)/layout.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/layout.tsx"),
    ("admin-web/src/app/(admin)/merchant/stores/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/merchant/stores/page.tsx"),
    ("admin-web/src/app/(admin)/merchant/business-config/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/merchant/business-config/page.tsx"),
    ("admin-web/src/app/(admin)/merchant/stores/[id]/business-config/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/merchant/stores/[id]/business-config/page.tsx"),
    ("admin-web/src/app/(admin)/product-system/products/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/product-system/products/page.tsx"),
]


def run(ssh, cmd, timeout=600, ignore_err=False):
    print(f"\n>>> {cmd}")
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    print(f"[exit_code={rc}]")
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed: {cmd}\n{err}")
    return out, err, rc


def main() -> int:
    print("=" * 60)
    print("[deploy] 营业管理入口收敛 PRD v1.0 部署开始")
    print("=" * 60)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)

    sftp = ssh.open_sftp()
    try:
        # 1) 上传文件
        for local_rel, remote_abs in FILES_TO_UPLOAD:
            local_abs = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.isfile(local_abs):
                raise FileNotFoundError(local_abs)
            remote_dir = os.path.dirname(remote_abs)
            run(ssh, f'mkdir -p "{remote_dir}"', ignore_err=True)
            print(f"[scp] {local_abs} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        # 2) 校验关键源码文件已上传
        run(ssh, f'grep -c "_migrate_business_config_unify_v1" {PROJECT_DIR}/backend/app/main.py')
        run(ssh, f'grep -c "booking_cutoff_minutes" {PROJECT_DIR}/backend/app/models/models.py')
        run(ssh, f'grep -c "StoreBookingConfigResponse" {PROJECT_DIR}/backend/app/schemas/order_enhancement.py')
        run(ssh, f'ls -la {PROJECT_DIR}/admin-web/src/app/\\(admin\\)/merchant/stores/\\[id\\]/business-config/page.tsx', ignore_err=True)

        # 3) 重建 backend + admin-web（前端涉及商品管理 / 编辑门店 / 营业管理新页 / 老页跳转 / 菜单去除）
        run(ssh, f"cd {PROJECT_DIR} && docker compose build backend admin-web", timeout=1800)
        run(ssh, f"cd {PROJECT_DIR} && docker compose up -d backend admin-web", timeout=300)

        # 4) 等待启动
        print("\n[等待 30 秒，让 backend 启动稳定]")
        time.sleep(30)

        # 5) 容器内执行 pytest 验证（非UI 自动化测试，关键路径 25 + 1）
        out, _, _ = run(
            ssh,
            f"docker exec {BACKEND_NAME} pytest tests/test_business_config_unify_v1.py -v 2>&1 | tail -50",
            timeout=600,
            ignore_err=True,
        )
        out2, _, _ = run(
            ssh,
            f"docker exec {BACKEND_NAME} pytest tests/test_order_enhancement.py::test_concurrency_limit_get -v 2>&1 | tail -20",
            timeout=300,
            ignore_err=True,
        )

        # 6) backend 启动日志重点
        run(
            ssh,
            f"docker logs --tail 200 {BACKEND_NAME} 2>&1 | grep -iE 'business_config_unify|Application startup|Uvicorn|ERROR' | tail -30",
            ignore_err=True,
        )

        # 7) DB 确认列已加
        run(
            ssh,
            f"docker exec {BACKEND_NAME} python -c \""
            f"import asyncio; from sqlalchemy import text; "
            f"from app.core.database import async_session as s\n"
            f"async def f():\n"
            f"    async with s() as db:\n"
            f"        r = (await db.execute(text(\\\"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='merchant_stores' AND column_name='advance_days'\\\")))\n"
            f"        print('store.advance_days exists =', r.scalar())\n"
            f"        r = (await db.execute(text(\\\"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='merchant_stores' AND column_name='booking_cutoff_minutes'\\\")))\n"
            f"        print('store.booking_cutoff_minutes exists =', r.scalar())\n"
            f"        r = (await db.execute(text(\\\"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='products' AND column_name='booking_cutoff_minutes'\\\")))\n"
            f"        print('product.booking_cutoff_minutes exists =', r.scalar())\n"
            f"asyncio.run(f())\"",
            ignore_err=True,
        )

        # 8) HTTP 抽测
        base = f"http://localhost/autodev/{PROJECT_ID}"
        run(ssh, f"curl -s -o /dev/null -w 'health=%{{http_code}}\\n' {base}/api/health")
        run(ssh, f"curl -s -o /dev/null -w 'admin_root=%{{http_code}}\\n' {base}/admin/")
        # 营业管理新页
        run(ssh, f"curl -s -o /dev/null -w 'merchant_stores=%{{http_code}}\\n' {base}/admin/merchant/stores")
        # API 鉴权前 422/401（无 token），但应不是 5xx
        run(ssh, f"curl -s -o /dev/null -w 'booking_config_no_auth=%{{http_code}}\\n' {base}/api/merchant/stores/1/booking-config")
        run(ssh, f"curl -s -o /dev/null -w 'concurrency_limit_no_auth=%{{http_code}}\\n' {base}/api/merchant/concurrency-limit?store_id=1")

        print("=" * 60)
        print("[deploy] 完成。请检查上方 pytest 结果。")
        print("=" * 60)
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
