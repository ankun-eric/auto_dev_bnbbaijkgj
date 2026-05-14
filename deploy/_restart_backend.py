#!/usr/bin/env python3
import paramiko, sys, time, requests
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd, timeout=300):
    print(f"\n>>> {cmd[:140]}")
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = []
    for line in iter(stdout.readline, ""):
        if not line: break
        sys.stdout.write(line); sys.stdout.flush()
        out.append(line)
    return "".join(out)

# 重启容器（不重建，因为是 volume mount）
run(f"cd {REMOTE_DIR} && (docker compose restart backend 2>&1 || docker-compose restart backend 2>&1) | tail -5")

# 等
for i in range(45):
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        if r.status_code in (200, 404):
            print(f"[OK] (第{i+1}次)")
            break
    except: pass
    time.sleep(2)

time.sleep(2)

# 日志
print("\n========== 启动日志（最近 100 行） ==========")
out = run(f"docker logs --tail 200 {PROJECT_ID}-backend 2>&1 | tail -100")

print("\n========== 迁移日志 ==========")
mig = run(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | grep -E 'migrate|aichat' | tail -30 || true")
print("\n========== 容器状态 ==========")
run(f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID}")

ssh.close()
