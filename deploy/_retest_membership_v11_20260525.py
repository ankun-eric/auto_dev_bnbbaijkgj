"""[旧会员体系废弃 v1.1] 单独上传修复后的测试并跑 pytest"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"


def run(client, cmd, timeout=600, ignore_err=False):
    print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}", flush=True)
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:], flush=True)
    if err.strip():
        print("STDERR:", err[-1500:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        sftp = client.open_sftp()
        local = os.path.join(base, "backend", "tests", "test_membership_v1.py")
        remote = f"{PROJ_DIR}/backend/tests/test_membership_v1.py"
        print(f"upload {local} -> {remote}")
        sftp.put(local, remote)
        sftp.close()

        run(client,
            f"docker cp '{remote}' '{BACKEND_CONTAINER}:/app/tests/test_membership_v1.py'",
            ignore_err=True)

        run(client,
            f"docker exec {BACKEND_CONTAINER} python -m pytest "
            f"tests/test_membership_v1.py --no-header -v 2>&1 | tail -100",
            timeout=300, ignore_err=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
