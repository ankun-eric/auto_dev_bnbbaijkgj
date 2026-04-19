"""Force git fetch latest and rebuild only the admin-web container.

The previous deploy used a stale ad9f585 ref because GitHub fetch failed.
This script retries git fetch with longer timeouts, resets to the latest
master, and rebuilds the affected containers.
"""
import os
import time
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_USER = os.environ.get("GIT_USER", "ankun-eric")
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    def run(cmd, timeout=600, check=False):
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

    # Set git remote with token
    run(f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL}")
    run(f"cd {PROJECT_DIR} && git config http.lowSpeedLimit 0 && git config http.lowSpeedTime 999999 && git config http.postBuffer 524288000")

    # Try git fetch with up to 5 attempts
    ok = False
    for attempt in range(5):
        print(f"\n--- git fetch attempt {attempt+1}/5 ---")
        # Use https.proxy=null and try
        _, _, code = run(
            f"cd {PROJECT_DIR} && timeout 300 git fetch origin master 2>&1",
            timeout=350,
        )
        if code == 0:
            ok = True
            break
        time.sleep(10)
    if not ok:
        print("WARNING: git fetch failed 5 times. Falling back to scp upload of local repo state.")
        # As fallback, upload only the affected admin-web/src/app directories that should exist
        # but for simplicity, we re-upload via tar
        import subprocess
        local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tarfile_local = os.path.join(local_root, "_admin_app_sync.tar.gz")
        # Build tar
        subprocess.run([
            "tar", "-czf", tarfile_local,
            "-C", os.path.join(local_root, "admin-web", "src"),
            "app",
        ], check=True)
        print(f"Built tar: {tarfile_local}")
        # Upload
        sftp = c.open_sftp()
        sftp.put(tarfile_local, f"{PROJECT_DIR}/_admin_app_sync.tar.gz")
        sftp.close()
        run(
            f"cd {PROJECT_DIR}/admin-web/src && rm -rf app && tar -xzf {PROJECT_DIR}/_admin_app_sync.tar.gz && rm {PROJECT_DIR}/_admin_app_sync.tar.gz",
            check=True,
        )
        os.remove(tarfile_local)
    else:
        run(f"cd {PROJECT_DIR} && git reset --hard origin/master && git clean -fd", check=True)

    run(f"cd {PROJECT_DIR} && git log -1 --oneline")

    # Rebuild only admin-web container (the one with missing pages)
    print("\n=== Rebuild admin-web ===")
    run(
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -40",
        timeout=900,
        check=True,
    )
    run(
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1 | tail -10",
        check=True,
    )

    # Wait for admin healthcheck-ish
    print("\n=== Wait 25s for admin to settle ===")
    time.sleep(25)
    run(f"docker ps --filter name={DEPLOY_ID}-admin --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    c.close()
    print("\n=== repull/redeploy admin done ===")


if __name__ == "__main__":
    main()
