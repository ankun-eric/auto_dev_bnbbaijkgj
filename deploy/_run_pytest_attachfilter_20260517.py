"""Run new pytest tests inside backend container."""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND_CT = f"{DEPLOY_ID}-backend"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def open_ssh():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PWD,
                timeout=30, look_for_keys=False, allow_agent=False)
    return cli


def run(cli, cmd, timeout=600):
    print(f"\n$ {cmd[:300]}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-5000:])
    if err.strip():
        print("STDERR:", err[-2000:])
    print(f"[exit={code}]")
    return code, out, err


def main():
    cli = open_ssh()
    try:
        # Check if pytest is installed
        code, out, _ = run(cli, f"docker exec {BACKEND_CT} which pytest 2>&1 || echo NOT_FOUND")
        if "NOT_FOUND" in out or "not found" in out.lower() or code != 0:
            print(">>> pytest not installed; installing in container")
            run(cli, f"docker exec {BACKEND_CT} pip install -i https://mirrors.cloud.tencent.com/pypi/simple/ --trusted-host mirrors.cloud.tencent.com pytest pytest-asyncio 2>&1 | tail -10", timeout=300)

        # Verify install
        run(cli, f"docker exec {BACKEND_CT} pytest --version 2>&1")

        # Show test file exists in container (we mounted code via COPY)
        run(cli, f"docker exec {BACKEND_CT} ls -la /app/tests/test_ai_home_actionbar_and_attachment_filter_20260517.py 2>&1")

        # Run the target test
        run(cli, f"docker exec -w /app {BACKEND_CT} python -m pytest tests/test_ai_home_actionbar_and_attachment_filter_20260517.py -v 2>&1 | tail -80", timeout=600)

        # Also run all tests collected with pytest in case
        print("\n=== Full pytest discovery & run (skip-on-error tests in legacy files) ===")
        run(cli, f"docker exec -w /app {BACKEND_CT} python -m pytest tests/test_ai_home_actionbar_and_attachment_filter_20260517.py tests/test_ai_home_3bugs_20260517.py -v 2>&1 | tail -50", timeout=600)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
