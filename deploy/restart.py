import subprocess, sys, os, time

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
WORK_DIR = f'/home/ubuntu/{DEPLOY_ID}'
VERSION_TAG = 'v20260607_231212'
BUILD_COMMIT = 'b22505c'

def run(cmd, **kw):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=WORK_DIR, **kw)
    if r.stdout: print(r.stdout)
    if r.stderr: print(r.stderr)
    return r

print("=== Stop services ===")
r = run("docker compose -f docker-compose.prod.yml down", timeout=60)
print("Services stopped")

print("=== Create .env ===")
env_content = f'BUILD_COMMIT=publish-{int(time.time())}\nDEPLOY_VERSION={VERSION_TAG}\n'
with open(os.path.join(WORK_DIR, '.env'), 'w') as f:
    f.write(env_content)
print(f".env: {env_content.strip()}")

print("=== Start services ===")
r = run("docker compose -f docker-compose.prod.yml up -d", timeout=900)
if r.returncode != 0:
    print("ERROR: docker compose up failed")
    sys.exit(1)

print("=== Wait for health ===")
max_wait = 30
for i in range(max_wait):
    time.sleep(5)
    r = run("docker compose -f docker-compose.prod.yml ps --format json", timeout=10)
    healthy = r.stdout.count('"Health":"healthy"')
    total = r.stdout.count('"Service":"')
    print(f"  [{i+1}/{max_wait}] {healthy}/{total} healthy")
    if healthy >= 2 and total >= 3:
        print("All healthy!")
        break
else:
    print("WARN: timeout waiting for health")
    run("docker compose -f docker-compose.prod.yml ps", timeout=10)

# Verify containers
run("docker ps --filter 'name=6b099ed3-' --format '{{.Names}} {{.Status}}'", timeout=10)

# Connect gateway to network (just in case)
run(f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true", timeout=10)

# Reload gateway
run("docker exec gateway-nginx nginx -t 2>&1 && docker exec gateway-nginx nginx -s reload 2>&1", timeout=30)

print("RESTART_SUCCESS")
