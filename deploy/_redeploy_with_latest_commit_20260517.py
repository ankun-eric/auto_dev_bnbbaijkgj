"""Re-pull latest commit and rebuild backend (test file missing on previous deploy)."""
from __future__ import annotations
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
import os
_GH_TOKEN = os.environ.get("GH_TOKEN", "<REDACTED_GH_TOKEN>")
GIT_URL = f"https://ankun-eric:{_GH_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
TARGET_COMMIT = "e803516"


def open_ssh():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, 22, USER, PWD, look_for_keys=False, allow_agent=False, timeout=30)
    return cli


def run(cli, cmd, timeout=900):
    print(f"\n$ {cmd[:280]}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-4500:])
    if err.strip():
        print("STDERR:", err[-1500:])
    print(f"[exit={code}]")
    return code, out, err


def main():
    cli = open_ssh()
    try:
        run(cli, f"cd {REMOTE_DIR} && git remote set-url origin '{GIT_URL}'")
        # Hard prune & fetch
        for attempt in range(3):
            code, _, _ = run(cli, f"cd {REMOTE_DIR} && timeout 90 git fetch origin master --no-tags 2>&1 | tail -10")
            if code == 0:
                break
            time.sleep(5)
        run(cli, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        run(cli, f"cd {REMOTE_DIR} && git log -1 --oneline")
        # Verify target file present
        run(cli, f"ls -la {REMOTE_DIR}/backend/tests/test_ai_home_actionbar_and_attachment_filter_20260517.py")

        # Rebuild backend & h5-web
        run(cli, f"cd {REMOTE_DIR} && BC=$(git log -1 --format='%H') && echo \"BUILD_COMMIT=$BC\" > .env.build && (grep -v '^BUILD_COMMIT=' .env > .env.tmp 2>/dev/null || true) && cat .env.build >> .env.tmp && mv .env.tmp .env && cat .env")
        # Rebuild backend
        run(cli, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -15", timeout=1500)
        # Rebuild h5
        run(cli, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -15", timeout=1800)
        # Restart
        run(cli, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend h5-web 2>&1 | tail -10")
        # Reconnect gateway
        run(cli, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")
        # Wait briefly
        time.sleep(10)
        run(cli, f"docker compose -f {REMOTE_DIR}/docker-compose.prod.yml -f {REMOTE_DIR}/docker-compose.yml ps 2>&1 | tail -10 || docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep -E '6b099ed3|gateway'")
        # Verify test file in container
        run(cli, f"docker exec {DEPLOY_ID}-backend ls /app/tests/test_ai_home_actionbar_and_attachment_filter_20260517.py 2>&1")
        # gateway reload + ssl check
        run(cli, f"docker exec gateway nginx -t && docker exec gateway nginx -s reload")
        time.sleep(2)
        # External check
        run(cli, f"curl -Is https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ 2>&1 | head -3")
        run(cli, f"curl -s https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
