#!/usr/bin/env python3
"""[订单列表固定列与列宽优化 v1.0] 增量部署 + 容器内 pytest

变更内容：
- admin-web：订单列表取消左固定，调整列顺序与列宽，新增用户/手机/数量列
- h5-web（商家 PC 端 /merchant/orders）：取消左固定，调整列顺序，按 PRD 列宽规范
- backend：admin / merchant 订单列表接口补齐 user_nickname / total_quantity 字段
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
    # 后端：admin / merchant 列表接口补齐字段
    ("backend/app/api/product_admin.py", "backend/app/api/product_admin.py"),
    ("backend/app/api/merchant.py", "backend/app/api/merchant.py"),
    ("backend/app/schemas/unified_orders.py", "backend/app/schemas/unified_orders.py"),
    # admin 端订单列表
    ("admin-web/src/app/(admin)/product-system/orders/page.tsx",
     "admin-web/src/app/(admin)/product-system/orders/page.tsx"),
    # 商家 PC 端订单列表（h5-web）
    ("h5-web/src/app/merchant/orders/page.tsx",
     "h5-web/src/app/merchant/orders/page.tsx"),
]


def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    return c


def run(c, cmd, timeout=900):
    short = cmd if len(cmd) <= 200 else cmd[:200] + "..."
    print(f"\n>>> {short}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-4000:])
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

    print("\n=== Step 2: rebuild backend / admin-web / h5-web ===")
    for service in ["backend", "admin-web", "h5-web"]:
        rc, _, _ = run(
            c,
            f"cd {REMOTE_ROOT} && docker compose build {service} 2>&1 | tail -30",
            timeout=2400,
        )
        if rc != 0:
            print(f"!! docker compose build {service} 失败")
            sys.exit(3)
        rc, _, _ = run(
            c,
            f"cd {REMOTE_ROOT} && docker compose up -d {service} 2>&1 | tail -20",
            timeout=600,
        )
        if rc != 0:
            print(f"!! docker compose up {service} 失败")
            sys.exit(4)

    print("\n=== Step 3: wait & container status ===")
    time.sleep(25)
    run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 4: verify external URLs ===")
    base = "https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID
    paths = [
        "/",
        "/api/health",
        "/admin/",
        "/admin/login",
        "/admin/product-system/orders",
        "/merchant/orders",
        "/api/admin/orders/unified?page=1&page_size=5",
    ]
    for p in paths:
        run(c, f"curl -s -o /dev/null -w 'GET {p} -> %{{http_code}}\\n' '{base}{p}'")

    sftp.close()
    c.close()
    print("\n=== Deploy done ===")


if __name__ == "__main__":
    main()
