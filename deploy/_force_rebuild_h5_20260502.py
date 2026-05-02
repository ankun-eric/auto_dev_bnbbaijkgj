# -*- coding: utf-8 -*-
"""强制 no-cache 重建 backend，并验证 h5_checkout 已被加载。"""
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND = f"{DEPLOY_ID}-backend"


def run(c, cmd, t=600):
    print(f"\n$ {cmd}")
    _i, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out[-4000:])
    if err.strip():
        print("stderr:", err[-1500:])
    print(f"exit={rc}")
    return rc, out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    try:
        # 确认仓库 git 是最新 commit
        run(c, f"cd {PROJECT_DIR} && git log -1 --oneline && git diff --stat HEAD~1 HEAD | head -30", t=20)
        # 确认 build context 中的关键文件存在
        run(c, f"ls -la {PROJECT_DIR}/backend/app/api/h5_checkout.py", t=10)
        run(c, f"grep -n h5_checkout {PROJECT_DIR}/backend/app/main.py", t=10)
        # 强制 no-cache 重建 backend
        rc, _ = run(c,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -50",
            t=900)
        if rc != 0:
            return rc
        run(c,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10",
            t=120)
        time.sleep(15)
        # 验证容器内 main.py 含 h5_checkout
        run(c, f"docker exec {BACKEND} grep -n h5_checkout /app/app/main.py")
        run(c, f"docker exec {BACKEND} ls /app/app/api/h5_checkout.py")
        # 重新探测
        run(c, f"docker exec {BACKEND} python -c \"import json,urllib.request as u; d=json.loads(u.urlopen('http://localhost:8000/openapi.json').read()); paths=[p for p in d.get('paths',{{}}).keys() if 'h5' in p]; print(paths)\"")
        # 通过 gateway curl
        run(c, f"curl -sk -o /dev/null -w 'init=%{{http_code}}\\n' 'https://localhost/autodev/{DEPLOY_ID}/api/h5/checkout/init?productId=1'")
        run(c, f"curl -sk -o /dev/null -w 'slots=%{{http_code}}\\n' 'https://localhost/autodev/{DEPLOY_ID}/api/h5/slots?storeId=1&date=2026-05-03&productId=1'")
    finally:
        c.close()


if __name__ == "__main__":
    main()
