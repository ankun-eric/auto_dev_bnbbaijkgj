import paramiko
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BUILD_COMMIT = "364ac25f8cca2b81eb0dc254fb0a9cae3046b059"
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

print("[1] Git pull from origin...")
out, err = run("git pull origin master 2>&1", timeout=30)
print(f"Pull: {out[:400]}")

print("\n[2] Stop containers...")
out, err = run("docker compose -f docker-compose.prod.yml down 2>&1", timeout=60)
print(f"Down: {out[:200]}")

print(f"\n[3] Build with BUILD_COMMIT={BUILD_COMMIT}...")
out, err = run(f"BUILD_COMMIT={BUILD_COMMIT} docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
lines = out.strip().split('\n')
for line in lines[-8:]:
    print(f"  {line}")

print("\n[4] Start containers...")
out, err = run("docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=60)
print(f"Up: {out[:200]}")

print("\n[5] Wait for healthy...")
for i in range(30):
    time.sleep(10)
    out, err = run("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'", timeout=10)
    print(f"  [{i+1}] {out}")
    lines = out.strip().split('\n')
    if lines and all('Up' in l for l in lines) and all('unhealthy' not in l.lower() for l in lines):
        healthy_count = sum(1 for l in lines if '(healthy)' in l)
        print(f"  All up! {healthy_count}/{len(lines)} healthy")
        if healthy_count == len(lines):
            break

print("\n[6] Reload gateway...")
out, err = run(f"cp {GATEWAY_CONF_SRC} {GATEWAY_CONF_DST} 2>&1")
out, err = run(f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
print(f"nginx -t: {out[:200]}")
out, err = run(f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
print(f"reload done")

print("\n[7] Verify HTTPS...")
out, err = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health 2>&1")
print(f"/api/health: HTTP {out}")
out, err = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/ 2>&1")
print(f"/ : HTTP {out}")
out, err = run(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/admin/ 2>&1")
print(f"/admin/: HTTP {out}")

print("\n[8] Final status...")
out, err = run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")
print(out)

print("\n[DONE]")
ssh.close()
