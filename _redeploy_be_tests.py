"""快速重新部署 backend 测试并跑回归"""
from __future__ import annotations
import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    "backend/tests/test_home_safety_v1.py",
]


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASSWORD, timeout=60, look_for_keys=False, allow_agent=False)
    c.get_transport().set_keepalive(30)
    return c


def sq(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def run(cli, cmd, sudo=False, timeout=300, check=True):
    full = f"echo {sq(PASSWORD)} | sudo -S bash -lc {sq(cmd)}" if sudo else cmd
    print(f"$ {cmd[:240]}")
    _, stdout, stderr = cli.exec_command(full, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print("[err]", err[-1000:])
    if check and rc != 0:
        raise RuntimeError(f"rc={rc}: {cmd}")
    return rc, out, err


def upload(sftp, local, remote):
    print(f"  upload {local} -> {remote}")
    sftp.put(local, remote)


def main():
    cli = ssh()
    sftp = cli.open_sftp()
    try:
        for f in FILES:
            upload(sftp, os.path.abspath(f), f"{PROJECT_DIR}/{f}")
        be = f"{DEPLOY_ID}-backend"
        for f in FILES:
            inner = "/app/" + f.split("/", 1)[1]  # tests/...
            run(cli, f"docker cp {PROJECT_DIR}/{f} {be}:{inner}", sudo=True)

        # 等待 backend 健康
        for i in range(40):
            rc, out, _ = run(
                cli,
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost/autodev/{DEPLOY_ID}/api/health",
                check=False,
            )
            if "200" in out:
                print(f"backend ok after {i+1}s")
                break
            time.sleep(2)

        run(
            cli,
            f"docker exec {be} python -m pytest "
            "tests/test_home_safety_v1.py "
            "tests/test_home_safety_v2.py "
            "tests/test_home_safety_v2_revision.py "
            "tests/test_home_safety_gwid_ephone_v1.py "
            "tests/test_home_safety_callback_datatype_v1.py "
            "tests/test_home_safety_member_v21.py "
            "tests/test_home_safety_remark_alarms_v1_20260529.py "
            "-v --tb=short",
            sudo=True,
            check=False,
            timeout=600,
        )

        # smoke
        base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for p in ["/api/health", "/home-safety/", "/admin/home-safety/", "/api/family/members"]:
            rc, out, _ = run(cli, f"curl -sk -o /dev/null -w '%{{http_code}}' {base}{p}", check=False)
            print(f"  GET {p} -> {out.strip()}")
    finally:
        sftp.close()
        cli.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL:", e)
        sys.exit(2)
