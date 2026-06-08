#!/usr/bin/env python3
"""Fix container name conflicts and restart deployment"""
import paramiko, time, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, timeout=60):
    print(f'\n[CMD] {cmd[:200]}')
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f'[OUT] {out.strip()[:1000]}')
    if err.strip():
        print(f'[ERR] {err.strip()[:500]}')
    print(f'[EXIT] {code}')
    sys.stdout.flush()
    return out, err, code

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# Step 1: Force stop and remove all project containers
print("=" * 60)
print("Step 1: Remove all old containers")
print("=" * 60)
run(f"docker ps -a --filter name={DEPLOY_ID} -q 2>/dev/null")
out, _, _ = run(f"docker ps -a --filter name={DEPLOY_ID} -q")
container_ids = [c for c in out.strip().split('\n') if c.strip()]
if container_ids:
    ids_str = ' '.join(container_ids)
    run(f"docker stop {ids_str} 2>/dev/null || true")
    run(f"docker rm -f {ids_str} 2>/dev/null || true")
    print(f"Removed {len(container_ids)} containers")
else:
    print("No containers found")

# Step 2: Ensure project network exists and db is connected
print("\n" + "=" * 60)
print("Step 2: Network setup")
print("=" * 60)
run(f"docker network create {DEPLOY_ID}-network 2>/dev/null || echo 'exists'")
run(f"docker network connect {DEPLOY_ID}-network db 2>/dev/null || echo 'already_connected'")

# Step 3: Docker compose up
print("\n" + "=" * 60)
print("Step 3: Start containers")
print("=" * 60)
project_dir = f"/home/ubuntu/{DEPLOY_ID}/deploy"
out, err, code = run(f"cd {project_dir} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=180)
if code != 0:
    print("Trying again after ensuring network...")
    run(f"docker network create {DEPLOY_ID}-network 2>/dev/null || echo 'exists'")
    run(f"cd {project_dir} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=180)

# Step 4: Wait and check
print("\n" + "=" * 60)
print("Step 4: Check status (waiting 20s)")
print("=" * 60)
time.sleep(20)

# Use simple format that works
run("docker ps --filter name=6b099ed3")

# Check logs
print("\n--- Backend logs (last 15) ---")
run(f"docker logs {DEPLOY_ID}-backend --tail 15 2>&1")

print("\n--- Admin logs (last 15) ---")
run(f"docker logs {DEPLOY_ID}-admin --tail 15 2>&1")

print("\n--- H5 logs (last 15) ---")
run(f"docker logs {DEPLOY_ID}-h5 --tail 15 2>&1")

# Step 5: HTTP verification
print("\n" + "=" * 60)
print("Step 5: HTTP verification")
print("=" * 60)
domain = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{domain}/api/health")
run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{domain}/")
run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{domain}/admin/")

# Reload nginx
print("\n--- Reloading gateway nginx ---")
run("docker exec gateway-nginx nginx -s reload 2>&1")

# Final HTTP check
print("\n--- Final HTTP check ---")
run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{domain}/admin/")

ssh.close()
print("\nDone!")
