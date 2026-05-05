"""在 backend 容器内安装 pytest 并运行支付宝私钥校验回归测试。"""
from __future__ import annotations

import sys
import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=900):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[:8000], flush=True)
    if err.strip():
        print(f"[STDERR] {err.strip()[:4000]}", flush=True)
    print(f"[EXIT {code}]", flush=True)
    return code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=60)
    print("Connected", flush=True)

    container = f"{DEPLOY_ID}-backend"

    # 1) 安装 pytest（容器中暂时安装，重启后会丢失，仅用于一次性校验）
    run(
        client,
        f"docker exec {container} pip install --no-cache-dir pytest pytest-asyncio aiosqlite "
        "-i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com",
        timeout=180,
    )

    # 2) 跑测试 —— 使用 --noconftest 跳过项目 conftest.py（不依赖 aiosqlite）
    code, _, _ = run(
        client,
        (
            f"docker exec {container} python -m pytest "
            "tests/test_alipay_private_key_format.py "
            "--noconftest -v --tb=short --no-header -p no:cacheprovider"
        ),
        timeout=300,
    )

    client.close()
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
