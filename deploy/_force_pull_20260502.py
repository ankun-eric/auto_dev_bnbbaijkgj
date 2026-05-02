# -*- coding: utf-8 -*-
"""强制远程 pull origin master 到 HEAD，并打印诊断。"""
from __future__ import annotations

import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
URL = f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"


def run(c, cmd, timeout=180):
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print("STDERR:", err[-2000:])
    code = o.channel.recv_exit_status()
    print(f"exit={code}")
    return code


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    try:
        run(c, f"cd {PROJECT_DIR} && git remote set-url origin {URL}")
        run(c, f"cd {PROJECT_DIR} && git fetch origin master --verbose 2>&1 | tail -30", timeout=300)
        run(c, f"cd {PROJECT_DIR} && git log -1 origin/master --oneline")
        run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master")
        run(c, f"cd {PROJECT_DIR} && git log -1 --oneline")
        run(c, f"cd {PROJECT_DIR} && grep -c 'type-descriptions' backend/app/api/coupons_admin.py")
        # 重启后端使代码生效
        run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -15", timeout=900)
        run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10", timeout=120)
        import time
        time.sleep(15)
        run(c, f"docker exec {DEPLOY_ID}-backend grep -c 'type-descriptions' /app/app/api/coupons_admin.py")
        run(c, f"docker exec {DEPLOY_ID}-backend python -c \"from app.api.coupons_admin import router; print(len([r for r in router.routes if 'type-desc' in r.path or 'scope-limits' in r.path or 'category-tree' in r.path or 'product-picker' in r.path or 'active-product' in r.path]))\"")
        # 通过 nginx 访问看返回码
        run(c, f"curl -sk -o /dev/null -w 'code=%{{http_code}}\\n' 'https://localhost/autodev/{DEPLOY_ID}/api/admin/coupons/type-descriptions'")
        run(c, f"curl -sk -o /dev/null -w 'code=%{{http_code}}\\n' 'https://localhost/autodev/{DEPLOY_ID}/api/admin/coupons/scope-limits'")
    finally:
        c.close()


if __name__ == "__main__":
    main()
