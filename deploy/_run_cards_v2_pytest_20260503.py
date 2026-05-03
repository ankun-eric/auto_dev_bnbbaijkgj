"""容器内运行 cards v2 pytest 套件（4 个文件）"""
from __future__ import annotations
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONTAINER = f"{DEPLOY_ID}-backend"


def run(ssh, cmd, timeout=600):
    print(f">>> {cmd[:300]}")
    _, so, se = ssh.exec_command(cmd, timeout=timeout)
    o = so.read().decode("utf-8", "ignore")
    e = se.read().decode("utf-8", "ignore")
    rc = so.channel.recv_exit_status()
    if o.strip():
        print(o.rstrip()[-6000:])
    if e.strip():
        print(f"[stderr] {e.rstrip()[-1500:]}")
    print(f"<<< exit={rc}\n")
    return rc, o, e


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # 安装测试依赖（如已装则秒过）
        run(
            ssh,
            f"docker exec {CONTAINER} pip install -q pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -5",
            timeout=180,
        )
        # 运行 cards_v2 4 个文件
        run(
            ssh,
            f"docker exec -e DATABASE_URL='sqlite+aiosqlite:///:memory:' {CONTAINER} "
            f"python -m pytest -v tests/test_cards_v2_purchase.py tests/test_cards_v2_redemption.py "
            f"tests/test_cards_v2_renew.py tests/test_cards_v2_dashboard.py 2>&1 | tail -80",
            timeout=900,
        )
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
