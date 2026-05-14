#!/usr/bin/env python3
"""Retry pull + redeploy backend only."""
from __future__ import annotations
import sys, time
import paramiko, requests

HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd, timeout=600):
    print(f"\n>>> {cmd[:140]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out=[]
    for line in iter(stdout.readline, ""):
        if not line: break
        sys.stdout.write(line); sys.stdout.flush()
        out.append(line)
    return stdout.channel.recv_exit_status(), "".join(out)

# 重试 git fetch 3 次（每次 90s）
for i in range(3):
    code, out = run(f"cd {REMOTE_DIR} && git fetch origin master --depth=10 2>&1 | tail -10", timeout=120)
    if "Operation too slow" not in out and "unable to access" not in out:
        break
    print(f"[retry {i+1}/3] git fetch slow, 等 5 秒再试")
    time.sleep(5)

run(f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
run(f"cd {REMOTE_DIR} && git log -3 --oneline")

# 验证关键提交
code, out = run(f"cd {REMOTE_DIR} && grep -c '\\[migrate\\] aichat_optim_fix_v1: 启动迁移' backend/app/main.py 2>&1 || echo 0")
if "0" in out.split()[-1]:
    print("[WARN] 代码可能未拉到最新")

# 重建 backend
run(f"cd {REMOTE_DIR} && (docker compose stop backend 2>&1 || docker-compose stop backend 2>&1) | tail -5")
run(f"cd {REMOTE_DIR} && (docker compose rm -f backend 2>&1 || docker-compose rm -f backend 2>&1) | tail -5")
run(f"cd {REMOTE_DIR} && (docker compose build backend 2>&1 || docker-compose build backend 2>&1) | tail -30", timeout=600)
run(f"cd {REMOTE_DIR} && (docker compose up -d backend 2>&1 || docker-compose up -d backend 2>&1) | tail -10")

# 等就绪
for i in range(45):
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        if r.status_code in (200, 404):
            print(f"[OK] backend OK (第{i+1}次)")
            break
    except: pass
    time.sleep(2)

time.sleep(3)
# 打印迁移日志
run(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | grep -E 'migrate|aichat' | tail -30 || true")

ssh.close()
