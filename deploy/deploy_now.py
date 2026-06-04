#!/usr/bin/env python3
"""Full deployment script for 6b099ed3 project."""
import paramiko, time, sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_URL = "https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"
ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def connect():
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30,
                   look_for_keys=False, allow_agent=False, banner_timeout=30)
    print("[OK] SSH connected")

def run(cmd, timeout=60):
    """Run command and return stdout."""
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    out = b""
    err = b""
    deadline = time.time() + timeout
    while not chan.exit_status_ready():
        if time.time() > deadline:
            break
        if chan.recv_ready():
            out += chan.recv(65536)
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(65536)
        time.sleep(0.1)
    try:
        out += chan.recv(65536)
    except:
        pass
    try:
        err += chan.recv_stderr(65536)
    except:
        pass
    result = out.decode(errors='replace')
    if err:
        err_str = err.decode(errors='replace')
        if err_str.strip():
            print(f"  [stderr]: {err_str[:500]}")
    return result, chan.exit_status


print("=" * 70)
print(f"DEPLOY: {DEPLOY_ID}")
print(f"Project: Bini Health - Bucket path migration tool")
print("=" * 70)

connect()

# ===== Step 1: ACR Login =====
print("\n[1/7] ACR Login...")
out, ec = run(f"docker login --username={ACR_USER} --password={ACR_PASS} {ACR_REGISTRY} 2>&1")
print(f"  ACR: {out.strip()[:200]}")

# ===== Step 2: Pull latest code =====
print("\n[2/7] Pull latest code from Git...")
# Use git fetch + reset to get latest
git_url_auth = f"https://{GIT_USER}:{GIT_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
out, ec = run(f"cd {PROJECT_DIR} && git fetch --depth=1 {git_url_auth} master 2>&1 && git reset --hard FETCH_HEAD 2>&1 && git clean -fd 2>&1", timeout=60)
print(f"  Git fetch: {out.strip()[:300]}")
out, ec = run(f"cd {PROJECT_DIR} && git log -1 --oneline 2>&1")
print(f"  Latest commit: {out.strip()}")

# ===== Step 3: Get BUILD_COMMIT =====
print("\n[3/7] Set BUILD_COMMIT...")
out, ec = run(f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>&1")
BUILD_COMMIT = out.strip()
print(f"  BUILD_COMMIT={BUILD_COMMIT}")

# ===== Step 4: Rebuild backend =====
print("\n[4/7] Rebuild backend container (no-cache)...")
out, ec = run(f"cd {PROJECT_DIR} && export BUILD_COMMIT='{BUILD_COMMIT}' && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1", timeout=600)
# Print last 500 chars of output
lines = out.strip().split('\n')
for line in lines[-20:]:
    print(f"  {line}")

# ===== Step 5: Restart backend =====
print("\n[5/7] Restart backend container...")
out, ec = run(f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1")
print(f"  {out.strip()[:300]}")

# Wait for backend health
print("  Waiting for backend healthy...")
for i in range(24):
    time.sleep(5)
    out, ec = run(f"docker inspect {DEPLOY_ID}-backend --format '{{{{.State.Health.Status}}}}' 2>&1")
    status = out.strip()
    print(f"  [{i+1}/24] Backend: {status}")
    if status == "healthy":
        print("  Backend is healthy!")
        break
else:
    print("  WARNING: Backend health check timeout")

# ===== Step 6: Fix nginx config =====
print("\n[6/7] Fix nginx config (add include for .server file)...")
# Check if include already exists
out, ec = run(f"grep '{DEPLOY_ID}.server' /home/ubuntu/gateway/nginx.conf 2>&1")
if DEPLOY_ID in out:
    print("  .server include already exists in nginx.conf")
else:
    print("  Adding include to nginx.conf...")
    # Backup nginx.conf
    out, ec = run(f"cp /home/ubuntu/gateway/nginx.conf /home/ubuntu/gateway/nginx.conf.bak.{int(time.time())} 2>&1")
    print(f"  Backup: {out.strip()}")
    
    # Add include before the closing brace of http block
    # Write Python script to temp file on server
    script = r'''import sys
with open('/home/ubuntu/gateway/nginx.conf', 'r') as f:
    content = f.read()
include_line = '    include /etc/nginx/conf.d/''' + DEPLOY_ID + r'''.server;\n'
if include_line.strip() not in content:
    last_brace = content.rfind('}')
    if last_brace > 0:
        content = content[:last_brace] + include_line + content[last_brace:]
        with open('/home/ubuntu/gateway/nginx.conf', 'w') as f:
            f.write(content)
        print('Added include line')
    else:
        print('ERROR: Could not find closing brace')
        sys.exit(1)
else:
    print('Include already present')
'''
    # Write script to remote server via heredoc
    write_cmd = f"cat > /tmp/insert_server_{DEPLOY_ID[:8]}.py << 'PYEOF'\n{script}\nPYEOF"
    out, ec = run(write_cmd)
    print(f"  Write script: {out.strip()}")
    # Execute script
    add_cmd = f"python3 /tmp/insert_server_{DEPLOY_ID[:8]}.py"
    out, ec = run(add_cmd)
    print(f"  {out.strip()}")
    
    # Test nginx config
    out, ec = run(f"docker exec gateway-nginx nginx -t 2>&1")
    print(f"  nginx -t: {out.strip()[:300]}")
    
    if ec == 0:
        # Reload nginx
        out, ec = run(f"docker exec gateway-nginx nginx -s reload 2>&1")
        print(f"  nginx reload: {out.strip()}")
    else:
        print("  ERROR: nginx config test failed, rolling back...")
        # Restore backup
        run(f"cp /home/ubuntu/gateway/nginx.conf.bak.* /home/ubuntu/gateway/nginx.conf 2>&1")

# ===== Step 7: Database migration =====
print("\n[7/7] Database migration...")
# Check if the migration script exists
out, ec = run(f"docker exec {DEPLOY_ID}-backend ls /app/migrations/migration_bucket_replace_20260604.py 2>&1")
print(f"  Migration file: {out.strip()}")

# Run the migration (dry-run first to verify)
print("  Running migration dry-run...")
out, ec = run(f"docker exec {DEPLOY_ID}-backend python /app/migrations/migration_bucket_replace_20260604.py --dry-run 2>&1", timeout=30)
if out:
    for line in out.strip().split('\n')[-20:]:
        print(f"  {line}")

# Run actual migration
print("  Running migration...")
out, ec = run(f"docker exec {DEPLOY_ID}-backend python /app/migrations/migration_bucket_replace_20260604.py 2>&1", timeout=120)
if out:
    for line in out.strip().split('\n')[-30:]:
        print(f"  {line}")

# ===== Verify =====
print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

# Check backend health
out, ec = run(f"curl -s http://localhost:8000/api/health 2>&1 || docker exec {DEPLOY_ID}-backend python -c \"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())\" 2>&1")
print(f"  Backend health: {out.strip()}")

# Check container status
out, ec = run(f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}' 2>&1")
print(f"\n  Containers:\n{out}")

# Verify nginx has our server
out, ec = run(f"docker exec gateway-nginx sh -c 'nginx -T 2>&1 | grep -c \"{DEPLOY_ID}\"' 2>&1")
count = out.strip()
print(f"\n  Nginx includes for {DEPLOY_ID}: {count}")

# Test HTTPS access
out, ec = run(f"curl -sk https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/api/health 2>&1")
print(f"\n  HTTPS health: {out.strip()[:200]}")

# Verify BUILD_INFO
out, ec = run(f"docker exec {DEPLOY_ID}-backend cat /app/BUILD_INFO 2>&1")
print(f"\n  BUILD_INFO: {out.strip()}")

print("\n" + "=" * 70)
print("DEPLOYMENT COMPLETED")
print(f"DEPLOY_ID: {DEPLOY_ID}")
print(f"Domain: https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com")
print("=" * 70)

client.close()
