# -*- coding: utf-8 -*-
"""快速重建 backend（默认使用缓存层 - 仅源码层不缓存）+ 重启。"""
import os
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND = f"{DEPLOY_ID}-backend"
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = (
    f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if GIT_TOKEN else
    "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


def run(c, cmd, t=600):
    print(f"\n$ {cmd}")
    _i, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err.strip():
        print("stderr:", err[-1000:])
    print(f"exit={rc}")
    return rc, out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    try:
        run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline", t=300)
        run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -20", t=900)
        run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10", t=120)
        time.sleep(15)
        run(c, f"docker logs --tail 30 {BACKEND}")
    finally:
        c.close()


if __name__ == "__main__":
    main()
