#!/usr/bin/env python3
"""Rebuild + recreate backend container with the latest local main.py."""
import paramiko, sys, time, requests

HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

# 1. SCP 上传 main.py 到 backend/app/main.py（仓库源码）
print("=== SCP main.py ===")
sftp = ssh.open_sftp()
sftp.put(r"C:\auto_output\bnbbaijkgj\backend\app\main.py",
         f"{REMOTE_DIR}/backend/app/main.py")
sftp.close()
print("[OK] main.py 已上传")

def run(cmd, timeout=600):
    print(f"\n>>> {cmd[:140]}")
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = []
    for line in iter(stdout.readline, ""):
        if not line: break
        sys.stdout.write(line); sys.stdout.flush()
        out.append(line)
    return "".join(out)

# 验证文件内容
run(f"grep -n '启动迁移' {REMOTE_DIR}/backend/app/main.py | head -5")
run(f"sed -n '1110,1125p' {REMOTE_DIR}/backend/app/main.py")

# 2. rebuild (no-cache 确保 main.py 重新拷贝进 image)
run(f"cd {REMOTE_DIR} && (docker compose stop backend 2>&1 || docker-compose stop backend 2>&1) | tail -3")
run(f"cd {REMOTE_DIR} && (docker compose rm -f backend 2>&1 || docker-compose rm -f backend 2>&1) | tail -3")
run(f"cd {REMOTE_DIR} && (docker compose build --no-cache backend 2>&1 || docker-compose build --no-cache backend 2>&1) | tail -30", timeout=900)
run(f"cd {REMOTE_DIR} && (docker compose up -d backend 2>&1 || docker-compose up -d backend 2>&1) | tail -5")

# 3. 等就绪
for i in range(60):
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        if r.status_code in (200, 404):
            print(f"[OK] (第{i+1}次)")
            break
    except: pass
    time.sleep(2)

time.sleep(2)
print("\n========== 迁移日志 ==========")
run(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | grep -E 'migrate|aichat' | tail -30 || true")
print("\n========== 容器状态 ==========")
run(f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID}")

ssh.close()
