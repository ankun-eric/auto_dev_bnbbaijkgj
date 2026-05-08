"""仅同步 tests 目录到容器并跑 pytest（避免 docker build 耗时）。"""
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_HOST = "newbb.test.bangbangvip.com"
REMOTE_USER = "ubuntu"
REMOTE_PASS = "Newbang888"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def ssh(cmd, timeout=900, header=""):
    if header:
        print(f"\n=== {header} ===")
    print(f"[REMOTE] $ {cmd[:200]}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS, timeout=30)
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    client.close()
    if out:
        print(out[-8000:])
    if err:
        print("STDERR:", err[-2000:])
    print(f"[rc={rc}]")
    return rc, out, err


def main():
    container = f"{DEPLOY_ID}-backend"
    ssh(
        f"cd {REMOTE_DIR} && git fetch --all && git reset --hard origin/master && git log -1 --format='HEAD=%h %s'",
        header="A: git pull",
    )
    # 把 tests 目录拷到容器里
    ssh(
        f"docker cp {REMOTE_DIR}/backend/tests {container}:/app/",
        header="B: copy tests into container",
    )
    rc, out, _ = ssh(
        f"docker exec -w /app {container} sh -c \"python -W ignore -m pytest tests/test_reschedule_dual_identity.py -p no:warnings --tb=short -q 2>&1 | tail -120\"",
        timeout=600,
        header="C: run pytest",
    )
    print("\n========== SUMMARY ==========")
    print("pytest rc =", rc)
    if rc == 0:
        print("OK pytest pass")
    else:
        print("FAIL pytest fail")


if __name__ == "__main__":
    main()
