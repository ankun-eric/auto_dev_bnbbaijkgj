#!/usr/bin/env python3
"""SCP main.py to server, rebuild backend, re-run tests."""
from __future__ import annotations
import sys, time
import paramiko, requests

HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

LOCAL_MAIN = r"C:\auto_output\bnbbaijkgj\backend\app\main.py"

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

# 1. SCP main.py 直接覆盖
print("=== SCP main.py 上传 ===")
sftp = ssh.open_sftp()
remote_main = f"{REMOTE_DIR}/backend/app/main.py"
sftp.put(LOCAL_MAIN, remote_main)
sftp.close()
print(f"[OK] {LOCAL_MAIN} → {remote_main}")

# 验证文件含新内容
run(f"grep -c '启动迁移' {remote_main}")

# 重建 backend
run(f"cd {REMOTE_DIR} && (docker compose stop backend 2>&1 || docker-compose stop backend 2>&1) | tail -5")
run(f"cd {REMOTE_DIR} && (docker compose rm -f backend 2>&1 || docker-compose rm -f backend 2>&1) | tail -5")
run(f"cd {REMOTE_DIR} && (docker compose build backend 2>&1 || docker-compose build backend 2>&1) | tail -20", timeout=600)
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
code, out = run(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | grep -E 'migrate|aichat' | tail -30 || true")
print("\n========== MIGRATE LOG SUMMARY ==========")
print(out if out else "(empty)")

# 跑测试
print(f"\n=== 测试 ===")
tests = []
# T1
r = requests.get(f"{BASE_URL}/api/health", timeout=15)
tests.append(("T1 /api/health", r.status_code == 200, f"HTTP {r.status_code}"))
# T3
r = requests.get(f"{BASE_URL}/api/function-buttons?is_enabled=true", timeout=20)
tests.append(("T3 公开 /api/function-buttons", r.status_code == 200 and isinstance(r.json(), list), f"HTTP {r.status_code} 返回 {len(r.json()) if r.status_code==200 else '?' } 条"))
# T8 capsule
r = requests.post(f"{BASE_URL}/api/analytics/track", json={"event": "capsule_click", "params": {"button_id":1,"button_name":"X","button_type":"quick_ask"}, "ts": int(time.time()*1000)}, timeout=15)
tests.append(("T8 capsule_click 埋点", r.status_code in (200,201,204), f"HTTP {r.status_code}"))
# T9 card_button_click
r = requests.post(f"{BASE_URL}/api/analytics/track", json={"event": "card_button_click", "params": {"button_id":1,"card_type":"upload"}, "ts": int(time.time()*1000)}, timeout=15)
tests.append(("T9 card_button_click 埋点", r.status_code in (200,201,204), f"HTTP {r.status_code}"))
# T10 / T12 from logs
tests.append(("T10 启动日志含 aichat_optim_fix_v1", "aichat_optim_fix_v1" in out, ""))
tests.append(("T12 启动日志含 func_grid 迁移", "func_grid" in out or "simplified" in out, ""))

for name, ok, info in tests:
    print(f"  {'✅' if ok else '❌'} {name}  {info}")

ssh.close()
