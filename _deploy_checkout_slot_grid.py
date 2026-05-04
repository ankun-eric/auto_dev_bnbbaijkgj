#!/usr/bin/env python3
"""[2026-05-04 用户端下单页时段网格化展示与满额置灰 PRD v1.0] 增量部署 + 容器内 pytest

涉及文件：
- 后端：backend/app/api/h5_checkout.py（新增 /checkout/info + 改造 /slots） +
       backend/tests/test_checkout_info_slot_grid.py（新增 9 用例）
- H5：h5-web/src/app/checkout/page.tsx（时段改 3 列网格 + 满额角标 + 日历置灰）
- 小程序：miniprogram/pages/checkout/index.{js,wxml,wxss}（同上）
- Flutter：flutter_app/lib/screens/product/checkout_screen.dart（GridView 3 列 + 角标
       + selectableDayPredicate）
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
    ("backend/app/api/h5_checkout.py", "backend/app/api/h5_checkout.py"),
    ("backend/tests/test_checkout_info_slot_grid.py",
     "backend/tests/test_checkout_info_slot_grid.py"),
    # H5
    ("h5-web/src/app/checkout/page.tsx", "h5-web/src/app/checkout/page.tsx"),
    # 小程序（小程序无需服务器部署，但同步上传到代码目录便于打包脚本读取）
    ("miniprogram/pages/checkout/index.js",
     "miniprogram/pages/checkout/index.js"),
    ("miniprogram/pages/checkout/index.wxml",
     "miniprogram/pages/checkout/index.wxml"),
    ("miniprogram/pages/checkout/index.wxss",
     "miniprogram/pages/checkout/index.wxss"),
    # Flutter（不影响服务器部署，但同步上传便于打包脚本读取）
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
        print(out[-4000:])
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
    time.sleep(25)
    run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 4: pytest in backend container ===")
    backend_container = f"{DEPLOY_ID}-backend"
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_checkout_info_slot_grid.py "
          f"{backend_container}:/app/tests/test_checkout_info_slot_grid.py")

    run(c, f"docker exec {backend_container} pip install --no-cache-dir "
          f"pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -6",
        timeout=300)

    rc, out, _ = run(
        c,
        f"docker exec -e PYTHONPATH=/app {backend_container} "
        f"python -m pytest tests/test_checkout_info_slot_grid.py "
        f"-v --tb=short 2>&1 | tail -180",
        timeout=900,
    )

    print("\n=== Step 5: verify external URLs ===")
    base = "https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID
    for path in [
        "/",
        "/api/health",
        "/checkout",
        "/api/h5/checkout/info?productId=1",  # 401 期待（未带 token）
        "/api/h5/slots?storeId=1&date=2026-05-10&productId=1",
    ]:
        run(c, f"curl -s -o /dev/null -w 'GET {path} -> %{{http_code}}\\n' '{base}{path}'")

    sftp.close()
    c.close()
    print("\n=== Deploy & test done ===")
    return rc


if __name__ == "__main__":
    sys.exit(main())
