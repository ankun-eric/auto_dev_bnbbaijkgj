"""在远程 backend 容器内安装 pytest 并跑 V2 测试。"""
from __future__ import annotations
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(ssh, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-8000:])
    if err.strip():
        print(f"[stderr]\n{err.rstrip()[-2000:]}")
    print(f"<<< exit={code}")
    return code, out, err


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        c1, _, _ = run(ssh, f"docker exec {DEPLOY_ID}-backend bash -lc "
                       "'pip install -q pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -10'",
                       timeout=300)
        c2, out, _ = run(ssh, f"docker exec {DEPLOY_ID}-backend python -m pytest "
                         "tests/test_orders_status_v2.py -q 2>&1 | tail -50",
                         timeout=600)
        return 0 if (c2 == 0 and "passed" in out and "failed" not in out) else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
