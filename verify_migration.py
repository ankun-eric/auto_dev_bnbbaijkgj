#!/usr/bin/env python3
"""Verify database migration and container status."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out, err

print("=== Deployment Verification ===\n")

# Container status
print("[Container Status]")
_, out, _ = run(f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}' | grep {DEPLOY_ID}")
print(out)

# DB migration check
print("\n[Database Migration - guide_count column]")
_, out, _ = run(f"docker exec {DEPLOY_ID}-db mysql -u root -pbini_health_2026 bini_health -e 'DESCRIBE health_profiles;' 2>/dev/null | grep guide_count")
if "guide_count" in out:
    print(f"  PASS: guide_count column exists: {out}")
else:
    print(f"  FAIL: guide_count column not found. Output: {out}")

# Backend logs (last 5 lines)
print("\n[Backend Logs (last 5 lines)]")
_, out, _ = run(f"docker logs {DEPLOY_ID}-backend --tail=5 2>&1")
print(out)

client.close()
