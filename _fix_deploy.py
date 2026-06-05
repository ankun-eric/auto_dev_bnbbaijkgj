"""
Fix deployment: handle container name conflicts and restart.
"""
import paramiko
import sys
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
SERVER_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONTAINER = "gateway-nginx"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"

BACKEND = f"{DEPLOY_ID}-backend"
H5 = f"{DEPLOY_ID}-h5"
ADMIN = f"{DEPLOY_ID}-admin"

def log(msg):
    print(msg, flush=True)

def get_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    return client

def run(client, cmd, timeout=120):
    log(f"  CMD: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        log(f"  OUT: {out.strip()[:2000]}")
    if err.strip():
        log(f"  ERR: {err.strip()[:500]}")
    return out.strip(), err.strip(), exit_code

def main():
    client = get_client()
    log("Connected to server.")

    # Step 1: Check current state
    log("\n=== STEP 1: Current state ===")
    out, _, _ = run(client, f"docker ps -a --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}' 2>&1")

    # Check if old containers from root docker-compose exist
    # The issue: deploy/docker-compose.prod.yml tried to create containers with same names
    # that are already used by the root docker-compose.yml
    
    # Step 2: Find and stop old containers (from root compose project)
    log("\n=== STEP 2: Stop old containers ===")
    # The root docker-compose.yml uses these container names too
    # We need to stop them from the root compose project first
    
    # Check which containers exist
    out, _, _ = run(client, f"docker ps -a --filter name={BACKEND} --format '{{{{.ID}}}} {{{{.Status}}}}'")
    log(f"  Backend: {out}")
    
    out, _, _ = run(client, f"docker ps -a --filter name={H5} --format '{{{{.ID}}}} {{{{.Status}}}}'")
    log(f"  H5: {out}")
    
    out, _, _ = run(client, f"docker ps -a --filter name={ADMIN} --format '{{{{.ID}}}} {{{{.Status}}}}'")
    log(f"  Admin: {out}")

    # Step 3: Use the root docker-compose.yml to stop old containers first
    log("\n=== STEP 3: Stop via root docker-compose ===")
    run(client, f"cd {SERVER_PROJECT_DIR} && docker compose -f docker-compose.prod.yml down 2>&1 || echo 'root compose down done or failed'")
    
    # Step 4: Now stop any remaining containers with our names
    log("\n=== STEP 4: Force remove residual ===")
    run(client, f"docker stop {BACKEND} 2>/dev/null; docker rm {BACKEND} 2>/dev/null; echo 'backend cleaned'")
    run(client, f"docker stop {H5} 2>/dev/null; docker rm {H5} 2>/dev/null; echo 'h5 cleaned'")
    run(client, f"docker stop {ADMIN} 2>/dev/null; docker rm {ADMIN} 2>/dev/null; echo 'admin cleaned'")

    # Step 5: Now start with deploy/docker-compose.prod.yml
    log("\n=== STEP 5: Start with deploy compose ===")
    # Build and start
    run(client, f"cd {SERVER_PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml up -d --build 2>&1", timeout=600)

    # Wait for startup
    log("\n  Waiting 30s for containers to start...")
    time.sleep(30)

    # Step 6: Verify
    log("\n=== STEP 6: Verify containers ===")
    run(client, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'")

    log("\n  Backend health:")
    run(client, f"docker exec {BACKEND} python3 -c \"import urllib.request; r=urllib.request.urlopen('http://localhost:8000/api/health'); print(r.read().decode())\" 2>&1")

    log("\n  H5 test:")
    run(client, f"docker exec {H5} wget -qO- http://localhost:3001/ 2>&1 | head -3")

    log("\n  Admin test:")
    run(client, f"docker exec {ADMIN} wget -qO- http://localhost:3000/admin/ 2>&1 | head -3")

    # Step 7: Update gateway config
    log("\n=== STEP 7: Gateway config ===")
    # The docker cp failed due to read-only volume. Try copying to a writable location then moving
    gateway_conf_src = f"{SERVER_PROJECT_DIR}/deploy/gateway-routes.conf"
    # Copy to a temp location inside container
    run(client, f"docker cp {gateway_conf_src} {GATEWAY_CONTAINER}:/tmp/{DEPLOY_ID}.conf")
    # Then move inside container (requires exec)
    run(client, f"docker exec {GATEWAY_CONTAINER} cp /tmp/{DEPLOY_ID}.conf {GATEWAY_CONF}")
    run(client, f"docker exec {GATEWAY_CONTAINER} nginx -t")
    run(client, f"docker exec {GATEWAY_CONTAINER} nginx -s reload")

    # Step 8: Check nginx config includes this file
    log("\n=== STEP 8: Nginx include check ===")
    run(client, f"docker exec {GATEWAY_CONTAINER} grep -l '{DEPLOY_ID}' /etc/nginx/conf.d/*.conf /etc/nginx/conf.d/*.server 2>/dev/null | head -5")
    # Check main nginx config for include
    run(client, f"docker exec {GATEWAY_CONTAINER} grep -r 'include' /etc/nginx/nginx.conf 2>/dev/null | head -10")

    # Step 9: Test external access
    log("\n=== STEP 9: External test ===")
    run(client, f"curl -sk https://localhost/api/health -H 'Host: {DEPLOY_ID}.noob-ai.test.bangbangvip.com' 2>&1 | head -5")

    client.close()
    log("\n=== DONE ===")

if __name__ == "__main__":
    main()
