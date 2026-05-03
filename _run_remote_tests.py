"""[先下单后预约 Bug 修复] 服务器非UI自动化测试。

在服务器 backend 容器内运行 pytest，覆盖：
- 新增的 test_book_after_pay_bugfix.py（6 用例）
- 相关订单回归（test_orders_status_v2.py / test_product_appointment_bugfix.py / test_orders_auto_progress.py）
"""

import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

TEST_FILES = [
    "tests/test_book_after_pay_bugfix.py",
    "tests/test_orders_status_v2.py",
    "tests/test_orders_auto_progress.py",
    "tests/test_product_appointment_bugfix.py",
]


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    files = " ".join(TEST_FILES)
    install_cmd = (
        f"docker exec {CONTAINER} bash -lc "
        f"\"pip install -q pytest pytest-asyncio httpx anyio aiosqlite 2>&1 | tail -5\""
    )
    print(f"$ {install_cmd}\n", flush=True)
    _, sout, serr = ssh.exec_command(install_cmd, timeout=300)
    sout.channel.recv_exit_status()
    print(sout.read().decode("utf-8", errors="replace"))

    cmd = (
        f"docker exec {CONTAINER} bash -lc "
        f"\"cd /app && python -m pytest {files} --tb=short -p no:warnings 2>&1 | head -200\""
    )
    print(f"$ {cmd}\n", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err)
    print(f"exit={code}")
    ssh.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
