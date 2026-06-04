"""
Fix2: pull from origin, apply healthcheck config, verify.
"""
import paramiko
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BUILD_COMMIT = "b0126a1cf95b8fe71b80f2f0d25c540c3e740a04"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
GATEWAY_CONF_SRC = f"{PROJECT_DIR}/gateway-routes.conf"
GATEWAY_CONF_DST = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server"
GATEWAY_CONTAINER = "gateway-nginx"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(f"cd {PROJECT_DIR} && {cmd}", timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace').strip(), stderr.read().decode('utf-8', errors='replace').strip()

print("=== Step 1: Git pull from origin ===")
out, err = run("git pull origin master 2>&1", timeout=30)
print(f"Pull: {out[:500]}")
if err:
    print(f"Err: {err[:300]}")

print("\n=== Step 2: Check healthchecks in compose ===")
out, err = run("grep -c healthcheck docker-compose.prod.yml")
print(f"healthcheck count: {out}")

out, err = run("grep -A2 healthcheck docker-compose.prod.yml")
print(f"healthcheck blocks:\n{out[:500]}")

print("\n=== Step 3: Recreate containers with healthchecks ===")
out, err = run("docker compose -f docker-compose.prod.yml down 2>&1", timeout=60)
print(f"Down: {out[:200]}")
out, err = run("docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=60)
print(f"Up: {out[:200]}")

print("\n=== Step 4: Wait for health ===")
for i in range(30):
    time.sleep(10)
    out, err = run("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'", timeout=10)
    print(f"  [{i+1}] {out}")
    lines = out.strip().split('\n')
    if lines and all('Up' in l for l in lines):
        print("  All containers up!")
        break

print("\n=== Step 5: Update gateway config ===")
out, err = run(f"cp {GATEWAY_CONF_SRC} {GATEWAY_CONF_DST} 2>&1")
print(f"cp done")
out, err = run(f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
print(f"nginx -t: {out[:200]}")
out, err = run(f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
print(f"reload done")

print("\n=== Step 6: Verify HTTPS ===")
out, err = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health 2>&1")
print(f"/api/health: HTTP {out}")
out, err = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/ 2>&1")
print(f"/ : HTTP {out}")
out, err = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/admin/ 2>&1")
print(f"/admin/: HTTP {out}")

print("\n=== Step 7: Check admin account via DB ===")
out, err = run(f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health -e \"SELECT id, username, role FROM users WHERE username='admin' LIMIT 1;\" 2>&1", timeout=10)
print(f"Admin user: {out}")

print("\n=== Step 8: Check DB ===")
out, err = run(f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 -e \"SHOW DATABASES;\" 2>&1", timeout=10)
print(f"Databases: {out}")

print("\n=== Step 9: Final status ===")
out, err = run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")
print(out)

print("\n=== DONE ===")
ssh.close()
