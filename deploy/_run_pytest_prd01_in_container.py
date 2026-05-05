"""[PRD-01] 容器内安装 pytest 并跑 PRD-01 测试 + 既有看板测试回归"""
from __future__ import annotations

import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONTAINER = f"{DEPLOY_ID}-backend"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600):
    print(f"\n[REMOTE] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[:1500])
    return code, out, err


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

    print("=== Step 1: 容器内安装 pytest（如已装则秒过） ===")
    run(
        ssh,
        f"docker exec {CONTAINER} pip install -q pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -5",
        timeout=240,
    )

    print("\n=== Step 2: 跑 PRD-01 单元测试 + 既有看板/改期通知测试回归 ===")
    code, out, _ = run(
        ssh,
        f"docker exec {CONTAINER} python -m pytest "
        f"tests/test_time_slots_unified_v1.py "
        f"tests/test_merchant_dashboard_v1.py "
        f"tests/test_reschedule_notification_v1.py "
        f"-v --noconftest --tb=short 2>&1 | tail -100",
        timeout=180,
    )
    pytest_pass = ("passed" in out and " failed" not in out)
    fail_phrase = "failed" in out and "0 failed" not in out

    print("\n=== Done ===")
    print(f"  pytest: {'PASS' if pytest_pass and not fail_phrase else 'FAIL'}")

    ssh.close()
    return 0 if (pytest_pass and not fail_phrase) else 1


if __name__ == "__main__":
    sys.exit(main())
