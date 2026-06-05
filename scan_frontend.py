"""扫描前端 (H5 + Admin) 路由。"""
import paramiko
import re
import json
import sys

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)
print("Connected", flush=True)

def run(cmd, timeout=20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

# ═══ H5 前端 ═══
print("\n=== H5 Frontend ===", flush=True)

# Check what's available
out, err = run(f'docker exec {DEPLOY_ID}-h5 ls /app/')
print(f"H5 /app/: {out.strip()}")

# Check for .next
out, err = run(f'docker exec {DEPLOY_ID}-h5 ls /app/.next 2>&1')
print(f"H5 .next/: {out.strip()[:500]}")

# Try to find pages manifest
out, err = run(f'docker exec {DEPLOY_ID}-h5 cat /app/.next/prerender-manifest.json 2>&1 | head -200')
print(f"H5 prerender-manifest: {out[:500]}")

# Check server/app directory
out, err = run(f'docker exec {DEPLOY_ID}-h5 find /app/.next/server/app -type f -name \"*.js\" 2>&1 | head -60')
print(f"H5 .next/server/app JS files: {out[:2000]}")

# Also check for routes-manifest
out, err = run(f'docker exec {DEPLOY_ID}-h5 cat /app/.next/routes-manifest.json 2>&1 | head -200')
print(f"H5 routes-manifest: {out[:1000]}")

# Try build-manifest
out, err = run(f'docker exec {DEPLOY_ID}-h5 ls /app/.next/server/pages 2>&1')
print(f"H5 server/pages: {out[:500]}")

# Check if there's a standalone output
out, err = run(f'docker exec {DEPLOY_ID}-h5 find /app -name \"*.js\" -path \"*pages*\" 2>&1 | head -30')
print(f"H5 pages JS: {out[:2000]}")

# ═══ Admin 前端 ═══
print("\n=== Admin Frontend ===", flush=True)

out, err = run(f'docker exec {DEPLOY_ID}-admin ls /app/')
print(f"Admin /app/: {out.strip()}")

out, err = run(f'docker exec {DEPLOY_ID}-admin ls /app/.next 2>&1')
print(f"Admin .next/: {out.strip()[:500]}")

out, err = run(f'docker exec {DEPLOY_ID}-admin find /app/.next/server/app -type f -name \"*.js\" 2>&1 | head -60')
print(f"Admin .next/server/app JS: {out[:2000]}")

out, err = run(f'docker exec {DEPLOY_ID}-admin cat /app/.next/routes-manifest.json 2>&1 | head -200')
print(f"Admin routes-manifest: {out[:1000]}")

ssh.close()
print("\nDone!", flush=True)
