#!/usr/bin/env python3
"""[订单列表固定列与列宽优化 v1.0] 安装 pytest + 跑测试 + 接口字段检查"""
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    return c


def run(c, cmd, timeout=900):
    print(f"\n>>> {cmd[:200]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-6000:])
    if err:
        print("STDERR:", err[-1500:])
    print(f"--- EXIT {rc} ---")
    return rc, out, err


def main():
    c = make_ssh()
    # 安装 pytest 与异步测试依赖
    run(
        c,
        f"docker exec {BACKEND} pip install --quiet pytest pytest-asyncio httpx 2>&1 | tail -10",
        timeout=180,
    )

    # 跑订单相关测试
    rc, out, _ = run(
        c,
        f"docker exec -e PYTHONPATH=/app {BACKEND} python -m pytest "
        f"tests/test_orders_status_v2.py "
        f"tests/test_order_bugfix_7tab.py "
        f"-x --tb=short -q 2>&1 | tail -120",
        timeout=900,
    )
    c.close()
    print(f"\nResult exit: {rc}")


if __name__ == "__main__":
    main()
