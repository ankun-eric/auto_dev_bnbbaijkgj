"""[F-11 改期通知三通道] 部署脚本：SCP 上传 3 个文件 + 重建 backend + pytest + URL 验证。"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    ("backend/app/services/reschedule_notification.py", f"{REMOTE_PROJ}/backend/app/services/reschedule_notification.py"),
    ("backend/app/api/unified_orders.py", f"{REMOTE_PROJ}/backend/app/api/unified_orders.py"),
    ("backend/tests/test_reschedule_notification_v1.py", f"{REMOTE_PROJ}/backend/tests/test_reschedule_notification_v1.py"),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n[REMOTE] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err)
    return code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

    sftp = ssh.open_sftp()

    print("\n=== Step 1: SCP 上传 3 个变更文件 ===")
    for local_rel, remote_abs in FILES:
        local_abs = LOCAL_ROOT / local_rel
        if not local_abs.exists():
            print(f"  [SKIP] {local_rel} 不存在")
            continue
        size = local_abs.stat().st_size
        print(f"  [PUT] {local_rel} ({size} bytes) -> {remote_abs}")
        sftp.put(str(local_abs), remote_abs)
    sftp.close()

    print("\n=== Step 2: 重建 backend 容器 ===")
    code, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build backend 2>&1 | tail -30",
        timeout=600,
    )
    if code != 0:
        print("[FAIL] backend build failed")
        return 1

    print("\n=== Step 3: docker compose up -d ===")
    run(ssh, f"cd {REMOTE_PROJ} && docker compose up -d backend 2>&1 | tail -10")

    print("\n=== Step 4: 等待容器启动 ===")
    time.sleep(8)

    print("\n=== Step 5: 容器内运行新增测试 ===")
    container = f"{DEPLOY_ID}-backend"
    code, out, _ = run(
        ssh,
        f"docker exec {container} python -m pytest tests/test_reschedule_notification_v1.py -v --tb=short 2>&1 | tail -60",
        timeout=120,
    )
    pytest_pass = ("passed" in out and "failed" not in out.split("=========")[-1])

    print("\n=== Step 6: URL 验证 ===")
    urls = [
        f"{BASE_URL}/api/health",
        f"{BASE_URL}/admin/login/",
        f"{BASE_URL}/",
        f"{BASE_URL}/admin/product-system/orders/dashboard/",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
    ]
    all_ok = True
    for u in urls:
        code, out, _ = run(ssh, f"curl -k -s -o /dev/null -w '%{{http_code}}' '{u}'", timeout=30)
        status = out.strip()
        ok = status in ("200", "308", "401", "302")
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark}] {u} -> {status}")
        if not ok:
            all_ok = False

    print("\n=== Done ===")
    print(f"  pytest: {'PASS' if pytest_pass else 'FAIL'}")
    print(f"  urls:   {'PASS' if all_ok else 'FAIL'}")

    ssh.close()
    return 0 if (pytest_pass and all_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
