"""在远程服务器的 backend 容器内运行后端测试。"""
from __future__ import annotations
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"


def run(ssh, cmd, timeout=900):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-12000:])
    if err.strip():
        print(f"[stderr]\n{err.rstrip()[-3000:]}")
    print(f"<<< exit={code}")
    return code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        # 检查 pytest 是否已安装
        run(ssh, f"docker exec {CONTAINER} python -c 'import pytest, pytest_asyncio; print(pytest.__version__)' 2>&1 || echo MISSING")
        # 安装 pytest（如缺）
        run(ssh, f"docker exec {CONTAINER} pip install -q pytest pytest-asyncio aiosqlite 2>&1 | tail -10")
        # 跑 v1.1 卡面测试 + 原有 v1 测试
        run(
            ssh,
            f"docker exec -w /app {CONTAINER} python -m pytest -x -v "
            f"tests/test_cards_v1.py tests/test_cards_v11_face.py 2>&1 | tail -200",
            timeout=900,
        )
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
