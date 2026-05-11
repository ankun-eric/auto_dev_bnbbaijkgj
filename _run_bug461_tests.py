"""仅在已部署的 backend 容器中跑 BUG-461 测试。"""
from __future__ import annotations

import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=60)

    def run(cmd: str, timeout: int = 1200, show_tail: int = 12000):
        _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(f"\n$ {cmd[:200]}")
        print(f"[rc={rc}]")
        if out:
            print(out[-show_tail:])
        if err and rc != 0:
            print("ERR:", err[-2000:])
        return rc, out, err

    backend_container = f"{DEPLOY_ID}-backend"
    # 安装测试依赖（幂等）
    run(
        f"docker exec {backend_container} sh -lc "
        f"'python -m pip install -q -i https://mirrors.cloud.tencent.com/pypi/simple "
        f"--trusted-host mirrors.cloud.tencent.com pytest pytest-asyncio aiosqlite httpx'",
        timeout=300,
    )
    rc, out, _ = run(
        f"docker exec {backend_container} sh -lc "
        f"'set -o pipefail; cd /app && python -m pytest tests/test_bug461_drawer_history.py -v --tb=short'",
        timeout=600,
    )
    ssh.close()
    ok = (rc == 0) and ("passed" in out)
    print("\n" + "=" * 60)
    print("BUG-461 pytest:", "PASS" if ok else "FAIL")
    print("=" * 60)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
