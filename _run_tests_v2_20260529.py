"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29] v2 测试回归

容器里没有 pytest 模块（rebuild 后丢失），先 pip install，再跑测试。
"""
from __future__ import annotations
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{DEPLOY_ID}-backend"


def ssh_connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                timeout=60, banner_timeout=60, auth_timeout=60,
                look_for_keys=False, allow_agent=False)
    cli.get_transport().set_keepalive(30)
    return cli


def run(cli, cmd, *, timeout=600, check=False, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip():
            print(out[-5000:])
        if err.strip():
            print(f"[stderr] {err[-1500:]}")
        print(f"[rc={rc}]")
    return rc, out, err


def main():
    cli = ssh_connect()

    print("=== Check pytest installed ===")
    rc, _, _ = run(cli, f"docker exec {BE} sh -c 'python -m pytest --version 2>&1'", check=False)
    if rc != 0:
        print("=== pytest not installed, installing... ===")
        run(cli, f"docker exec {BE} sh -c 'pip install pytest pytest-asyncio aiosqlite httpx --quiet 2>&1 | tail -10'",
            timeout=300, check=False)

    print("=== Run pytest v1 + v2 ===")
    rc, out, err = run(
        cli,
        f"docker exec {BE} sh -c 'cd /app && python -m pytest "
        f"tests/test_guardian_bugfix_v1_20260529.py "
        f"tests/test_guardian_bugfix_v2_20260529.py "
        f"-v --tb=short 2>&1'",
        timeout=900,
    )
    cli.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
