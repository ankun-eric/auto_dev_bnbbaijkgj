# -*- coding: utf-8 -*-
"""强制服务器从 origin 拉最新到 5ff4424，并 no-cache 重建 backend。

策略：
- 删 .git/shallow（如有）
- git fetch --unshallow / fetch all
- git reset --hard origin/master
- 验证关键文件存在
- no-cache 重建 + up
"""
import time
import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND = f"{DEPLOY_ID}-backend"
TARGET = "5ff4424"

GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = (
    f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if GIT_TOKEN
    else "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


def run(c, cmd, t=600):
    print(f"\n$ {cmd}")
    _i, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out[-3500:])
    if err.strip():
        print("stderr:", err[-1500:])
    print(f"exit={rc}")
    return rc, out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    try:
        run(c, f"cd {PROJECT_DIR} && git remote -v && cat .git/HEAD && ls -la .git/shallow 2>/dev/null || true", t=10)
        run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL}", t=10)
        # 取消 shallow
        run(c, f"cd {PROJECT_DIR} && rm -f .git/shallow", t=5)
        # 多次 fetch
        for i in range(3):
            rc, _ = run(c, f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 600 git fetch origin master 2>&1 | tail -10", t=700)
            if rc == 0:
                break
            time.sleep(5)
        run(c, f"cd {PROJECT_DIR} && git log -1 origin/master --oneline", t=10)
        run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", t=15)
        run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", t=10)
        # 验证关键文件
        run(c, f"ls -la {PROJECT_DIR}/backend/app/api/h5_checkout.py {PROJECT_DIR}/h5-web/src/app/checkout/page.tsx", t=10)
        run(c, f"grep -c h5_checkout {PROJECT_DIR}/backend/app/main.py", t=10)
        # no-cache 重建 backend + h5-web + admin-web
        for svc in ("backend", "h5-web", "admin-web"):
            print(f"\n== rebuild {svc} ==")
            rc, _ = run(c,
                f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache {svc} 2>&1 | tail -25",
                t=1500)
            if rc != 0:
                print(f"!! {svc} build failed")
                return rc
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web admin-web 2>&1 | tail -15",
            t=120)
        time.sleep(20)
        # 验证
        run(c, f"docker exec {BACKEND} grep -c h5_checkout /app/app/main.py")
        run(c, f"docker exec {BACKEND} ls /app/app/api/h5_checkout.py")
        run(c, f"docker exec {BACKEND} python -c \"import json,urllib.request as u; d=json.loads(u.urlopen('http://localhost:8000/openapi.json').read()); paths=[p for p in d.get('paths',{{}}).keys() if 'h5' in p]; print(paths)\"")
        # gateway
        run(c, "docker exec gateway nginx -s reload 2>&1")
        run(c, f"curl -sk -o /dev/null -w 'init=%{{http_code}}\\n' 'https://localhost/autodev/{DEPLOY_ID}/api/h5/checkout/init?productId=1'")
        run(c, f"curl -sk -o /dev/null -w 'slots=%{{http_code}}\\n' 'https://localhost/autodev/{DEPLOY_ID}/api/h5/slots?storeId=1&date=2026-05-03&productId=1'")
    finally:
        c.close()


if __name__ == "__main__":
    main()
