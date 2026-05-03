"""强制重试 git fetch 并验证 database.py 内容，再跑 pytest"""
from __future__ import annotations
import os
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
REPO_URL = f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
CONTAINER = f"{DEPLOY_ID}-backend"


def run(ssh, cmd, timeout=600):
    print(f">>> {cmd[:300]}")
    _, so, se = ssh.exec_command(cmd, timeout=timeout)
    o = so.read().decode("utf-8", "ignore")
    e = se.read().decode("utf-8", "ignore")
    rc = so.channel.recv_exit_status()
    if o.strip():
        print(o.rstrip()[-3000:])
    if e.strip():
        print(f"[err] {e.rstrip()[-1000:]}")
    print(f"<<< rc={rc}\n")
    return rc, o, e


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        run(ssh, f"cd {PROJ_DIR} && git remote set-url origin '{REPO_URL}'")
        # 多次重试 fetch
        for i in range(5):
            rc, o, _ = run(
                ssh,
                f"cd {PROJ_DIR} && git fetch origin master 2>&1",
                timeout=300,
            )
            if rc == 0 and "fatal" not in o.lower():
                break
            print(f"[retry {i+1}/5] fetch failed, sleeping 10s")
            time.sleep(10)
        run(ssh, f"cd {PROJ_DIR} && git reset --hard origin/master 2>&1 | tail -3")
        run(ssh, f"cd {PROJ_DIR} && git log -1 --format='%H %s'")
        run(ssh, f"cd {PROJ_DIR} && head -20 backend/app/core/database.py")
        run(
            ssh,
            f"cd {PROJ_DIR} && docker compose build backend 2>&1 | tail -5",
            timeout=900,
        )
        run(
            ssh,
            f"cd {PROJ_DIR} && docker compose up -d --force-recreate backend 2>&1 | tail -5",
        )
        time.sleep(15)
        run(
            ssh,
            f"docker exec {CONTAINER} head -20 app/core/database.py",
        )
        run(
            ssh,
            f"docker exec {CONTAINER} pip install -q pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -2",
        )
        run(
            ssh,
            f"docker exec -e DATABASE_URL='sqlite+aiosqlite:///:memory:' {CONTAINER} "
            f"python -m pytest tests/test_cards_v2_purchase.py tests/test_cards_v2_redemption.py "
            f"tests/test_cards_v2_renew.py tests/test_cards_v2_dashboard.py -q 2>&1 | tail -50",
            timeout=900,
        )
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
