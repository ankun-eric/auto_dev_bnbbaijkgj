"""Rebuild backend container with the latest source from git origin/master."""
import os
import time
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    def run(cmd, timeout=900, check=False):
        print(f"\n$ {cmd[:200]}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out[-2500:])
        if err:
            print(f"[stderr] {err[-1000:]}")
        print(f"[exit {code}]")
        if check and code != 0:
            raise RuntimeError(cmd)
        return out, err, code

    run(f"cd {PROJECT_DIR} && git log -1 --oneline")
    # Verify the new files are on disk
    run(f"ls -la {PROJECT_DIR}/backend/app/api/coupons_admin.py")
    run(f"grep -c 'offline-reason-options' {PROJECT_DIR}/backend/app/api/coupons_admin.py")
    run(f"grep -c 'redeem-code-batches' {PROJECT_DIR}/backend/app/api/coupons_admin.py")

    # Force rebuild backend with --no-cache to bust any cached layers
    print("\n=== Rebuild backend (no-cache) ===")
    run(
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -50",
        timeout=900,
        check=True,
    )
    run(
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10",
        check=True,
    )
    time.sleep(20)
    run(f"docker ps --filter name={DEPLOY_ID}-backend --format '{{{{.Names}}}}\t{{{{.Status}}}}'")
    run(f"docker logs {DEPLOY_ID}-backend --tail 30 2>&1")

    c.close()
    print("\n=== backend rebuild done ===")


if __name__ == "__main__":
    main()
