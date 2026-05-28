"""[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 远程在 backend 容器内跑 home_safety 全套测试"""
from __future__ import annotations
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def sq(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def run(cli, cmd, timeout=600, check=False):
    print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-6000:])
    if err.strip():
        print(f"[stderr] {err[-1500:]}")
    print(f"[rc={rc}]")
    return rc, out, err


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD,
                timeout=60, look_for_keys=False, allow_agent=False)
    cli.get_transport().set_keepalive(30)

    cmd = (
        f"docker exec {BACKEND} sh -c "
        + sq(
            "cd /app && pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -5 && "
            "python -m pytest "
            "tests/test_home_safety_v1.py "
            "tests/test_home_safety_v2.py "
            "tests/test_home_safety_v2_revision.py "
            "tests/test_home_safety_callback_schema_sync_v1.py "
            "tests/test_home_safety_gwid_ephone_v1.py "
            "-v --tb=short --no-header 2>&1 | tail -250"
        )
    )
    rc, out, err = run(cli, cmd, timeout=900)
    cli.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
