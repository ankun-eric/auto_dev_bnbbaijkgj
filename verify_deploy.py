#!/usr/bin/env python3
"""Verify deployment and run automated tests."""
import paramiko
import time

HOST = "newbb.bangbangvip.com"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
CONTAINER_NAME = f"{DEPLOY_ID}-admin"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username="ubuntu", password="Newbang888", timeout=30)


def run(cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err:
        print("STDERR:", err[:1000])
    return out, err


# Check what's in the running container
print("=== Check container app directory ===")
run(f'docker exec {CONTAINER_NAME} sh -c "ls /app/"')
run(f'docker exec {CONTAINER_NAME} sh -c "ls /app/.next/ 2>/dev/null || echo no_next"')
run(f'docker exec {CONTAINER_NAME} sh -c "cat /app/.next/BUILD_ID 2>/dev/null || echo no_build_id"')

# The issue: standalone puts files at /app/ but container was configured differently
# Let's check what server.js exists
run(f'docker exec {CONTAINER_NAME} sh -c "ls /app/*.js 2>/dev/null || echo no_js_files"')

# Check what the container actually runs
run(f'docker exec {CONTAINER_NAME} sh -c "cat /proc/1/cmdline | tr \'\\0\' \' \'"')

# Check container file system more carefully
run(f'docker exec {CONTAINER_NAME} sh -c "find /app -maxdepth 2 -name \'*.js\' | head -10"')

print("\n=== Health checks ===")
run(f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/admin/ --max-time 30")
run(f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/health --max-time 30")

# Check if new build_id is there (build happened at ~11:35 server time)
run(f'docker exec {CONTAINER_NAME} sh -c "find / -name BUILD_ID 2>/dev/null | head -5"')
run(f'docker exec {CONTAINER_NAME} sh -c "stat /app/server.js 2>/dev/null || echo no server.js at root"')

client.close()
