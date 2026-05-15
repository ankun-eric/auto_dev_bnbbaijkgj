#!/usr/bin/env python3
"""修复 backend 容器网络（连上 DB 所在的网络）"""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
# DB 实际所在的 network（compose project prefix）
DB_NETWORK = f"{DEPLOY_ID}_{DEPLOY_ID}-network"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd, t=300):
    print(f"\n$ {cmd[:140]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(f"[err] {err.rstrip()}")
    return rc, out

# 1. 把 backend 也连到 DB 所在的 network
run(f"docker network connect {DB_NETWORK} {DEPLOY_ID}-backend --alias {DEPLOY_ID}-db-alias 2>&1 || true")
# 不需要 alias，去掉
run(f"docker network disconnect {DB_NETWORK} {DEPLOY_ID}-backend 2>&1 || true")
run(f"docker network connect {DB_NETWORK} {DEPLOY_ID}-backend 2>&1 || true")
# 把 h5 也连过去（一致性）
run(f"docker network connect {DB_NETWORK} {DEPLOY_ID}-h5 2>&1 || true")

# 2. 等 backend 健康
time.sleep(10)
for i in range(1, 15):
    rc, out = run(f"docker ps --filter name={DEPLOY_ID}-backend --format '{{{{.Status}}}}'")
    print(f"[wait {i}] {out.strip()}")
    if "Restarting" not in out and out.strip().startswith("Up"):
        break
    time.sleep(5)

run(f"docker logs --tail 10 {DEPLOY_ID}-backend 2>&1 | tail -10")
run(f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")
c.close()
