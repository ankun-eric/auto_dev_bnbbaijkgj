"""在远程 backend 容器内安装 pytest 并跑本次新增 + 回归测试."""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    return out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        # 检查 pytest 是否已安装
        out, _ = run(client, f"docker exec {DID}-backend python -c 'import pytest; print(pytest.__version__)' 2>&1")
        if "ModuleNotFoundError" in out or "No module" in out:
            print(">>> pytest 不存在，安装中...")
            run(client, (
                f"docker exec {DID}-backend pip install --quiet "
                f"-i https://mirrors.cloud.tencent.com/pypi/simple "
                f"--trusted-host mirrors.cloud.tencent.com "
                f"pytest pytest-asyncio httpx aiosqlite"
            ), timeout=300)

        # 运行测试
        run(client, (
            f"docker exec -e PYTEST_CURRENT_TEST=1 {DID}-backend "
            f"python -m pytest "
            f"tests/test_points_mall_detail_button_state.py "
            f"tests/test_points_mall_v11.py "
            f"-v --tb=short"
        ), timeout=600)
    finally:
        client.close()


if __name__ == "__main__":
    main()
