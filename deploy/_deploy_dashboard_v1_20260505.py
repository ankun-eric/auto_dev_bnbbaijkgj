#!/usr/bin/env python3
"""[门店预约看板与改期能力升级 v1.0] 部署脚本

策略：通过 paramiko SCP/SFTP 上传变更文件 → docker compose build → up → 验证
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
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

FILES_TO_UPLOAD: list[tuple[str, str]] = [
    # 后端
    ("backend/app/api/merchant_dashboard.py", f"{PROJECT_DIR}/backend/app/api/merchant_dashboard.py"),
    ("backend/app/main.py", f"{PROJECT_DIR}/backend/app/main.py"),
    ("backend/tests/test_merchant_dashboard_v1.py", f"{PROJECT_DIR}/backend/tests/test_merchant_dashboard_v1.py"),
    # admin-web
    (
        "admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx",
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx",
    ),
    (
        "admin-web/src/app/(admin)/product-system/orders/page.tsx",
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/product-system/orders/page.tsx",
    ),
]


def run(ssh, cmd, timeout=600, ignore_err=False):
    print(f"\n>>> {cmd}", flush=True)
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
    print("=" * 70)
    print("[deploy] 门店预约看板与改期能力升级 v1.0 部署开始")
    print("=" * 70)
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
            print(f"[scp] {local_abs} -> {remote_abs}", flush=True)
            sftp.put(local_abs, remote_abs)
        sftp.close()

        # 2) 校验关键源码文件已上传
        run(ssh, f'grep -c "merchant_dashboard" {PROJECT_DIR}/backend/app/main.py')
        run(ssh, f'grep -c "SLOT_HOURS" {PROJECT_DIR}/backend/app/api/merchant_dashboard.py')
        run(
            ssh,
            f"ls -la {PROJECT_DIR}/admin-web/src/app/\\(admin\\)/product-system/orders/dashboard/page.tsx",
            ignore_err=True,
        )

        # 3) 重建 backend + admin-web
        run(ssh, f"cd {PROJECT_DIR} && docker compose build backend admin-web", timeout=1800)
        run(ssh, f"cd {PROJECT_DIR} && docker compose up -d backend admin-web", timeout=300)

        # 4) 等待启动
        print("\n[等待 25 秒，让 backend 启动稳定]", flush=True)
        time.sleep(25)

        # 5) 容器内 pytest 验证
        out, _, rc = run(
            ssh,
            f"docker exec {BACKEND_NAME} python -m pytest tests/test_merchant_dashboard_v1.py -v 2>&1 | tail -40",
            timeout=300,
            ignore_err=True,
        )
        if rc != 0 or "passed" not in out:
            print("[WARN] pytest 输出未见 passed，请检查上方日志")

        # 6) 健康 + 接口连通性
        run(
            ssh,
            f"curl -sk -o /dev/null -w 'health: %{{http_code}}\\n' {BASE_URL}/api/health",
            ignore_err=True,
        )
        run(
            ssh,
            f"curl -sk -o /dev/null -w 'time-slots: %{{http_code}}\\n' {BASE_URL}/api/merchant/dashboard/time-slots",
            ignore_err=True,
        )
        run(
            ssh,
            f"curl -sk -L -o /dev/null -w 'orders: %{{http_code}}\\n' {BASE_URL}/admin/product-system/orders/",
            ignore_err=True,
        )
        run(
            ssh,
            f"curl -sk -L -o /dev/null -w 'dashboard: %{{http_code}}\\n' {BASE_URL}/admin/product-system/orders/dashboard/",
            ignore_err=True,
        )
        run(
            ssh,
            f"curl -sk -o /dev/null -w 'day_no_auth: %{{http_code}}\\n' "
            f"{BASE_URL}/api/merchant/dashboard/day?date=2026-05-05",
            ignore_err=True,
        )

        print("\n" + "=" * 70)
        print("[deploy] 部署流程完成")
        print("=" * 70)
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
