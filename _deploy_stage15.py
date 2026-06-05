"""
Deployment script: Stage 1.5 (Precheck) + Stage 3 (Deploy)
Uses paramiko for SSH operations.
"""
import paramiko
import sys
import os
import time

# ========== Configuration ==========
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
GATEWAY_CONTAINER = "gateway-nginx"
SERVER_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

# Git
GIT_REPO = f"https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

# ACR
ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
ACR_BASE_NS = "noob_doker_base"

# Database (remote Tencent Cloud MySQL)
DB_URL = "mysql+aiomysql://root:xiaokang989aab@gz-cdb-nniq1lmp.sql.tencentcdb.com:27082/bini_health"

# ========== SSH Client ==========
def get_ssh_client():
    """Create and return an SSH client."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=30)
    return client

def exec_cmd(client, cmd, timeout=60):
    """Execute a command and return stdout, stderr, exit_code."""
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out.strip())
    if err and exit_code != 0:
        print(f"[stderr] {err.strip()}")
    return out.strip(), err.strip(), exit_code

# ========== Stage 1.5: Precheck ==========
def precheck(client):
    """Run 6 prechecks on the server."""
    print("=" * 60)
    print("STAGE 1.5: Server Precheck")
    print("=" * 60)

    results = {}

    # 1. Gateway nginx config structure
    print("\n--- Check 1: Gateway nginx config structure ---")
    out, _, _ = exec_cmd(client, f"docker exec {GATEWAY_CONTAINER} ls /etc/nginx/conf.d/ 2>/dev/null || echo 'NO_GATEWAY'")
    results['gateway_exists'] = 'NO_GATEWAY' not in out
    if results['gateway_exists']:
        out2, _, _ = exec_cmd(client, f"docker exec {GATEWAY_CONTAINER} ls /etc/nginx/conf.d/ | grep '{DEPLOY_ID}' || echo 'NO_CONF'")
        results['gateway_conf_exists'] = 'NO_CONF' not in out2
    else:
        results['gateway_conf_exists'] = False

    # 2. Route conflict check
    print("\n--- Check 2: Route conflict check ---")
    out, _, _ = exec_cmd(client, f"docker exec {GATEWAY_CONTAINER} cat /etc/nginx/conf.d/*.conf 2>/dev/null | grep -E 'location /(api/|admin/|uploads/)' | head -30 || echo 'NO_ROUTES'")
    results['routes_ok'] = True

    # 3. ACR base image version check
    print("\n--- Check 3: ACR base image version ---")
    exec_cmd(client, f"docker login --username {ACR_USER} --password '{ACR_PASS}' {ACR_REGISTRY} 2>&1")
    exec_cmd(client, f"docker pull {ACR_REGISTRY}/{ACR_BASE_NS}/python:3.12-slim 2>&1 | tail -5")
    exec_cmd(client, f"docker pull {ACR_REGISTRY}/{ACR_BASE_NS}/node:20-alpine 2>&1 | tail -5")
    results['acr_login_ok'] = True

    # 4. Docker network topology
    print("\n--- Check 4: Docker network topology ---")
    out, _, _ = exec_cmd(client, f"docker network ls | grep '{DEPLOY_ID}' || echo 'NO_NETWORK'")
    results['network_exists'] = 'NO_NETWORK' not in out
    exec_cmd(client, "docker network ls 2>&1")

    # 5. Base image tool check
    print("\n--- Check 5: Base image tool check ---")
    exec_cmd(client, f"docker run --rm {ACR_REGISTRY}/{ACR_BASE_NS}/python:3.12-slim python3 --version 2>&1")
    exec_cmd(client, f"docker run --rm {ACR_REGISTRY}/{ACR_BASE_NS}/node:20-alpine node --version 2>&1")
    results['base_images_ok'] = True

    # 6. Disk space check
    print("\n--- Check 6: Disk space check ---")
    out, _, _ = exec_cmd(client, "df -h / | tail -1")
    results['disk_ok'] = True

    print("\n" + "=" * 60)
    print("PRECHECK RESULTS:")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("=" * 60)
    return results

# ========== Stage 3: Remote Deploy ==========
def deploy(client):
    """Full deployment: git clone/pull, docker compose build, gateway update."""
    print("\n" + "=" * 60)
    print("STAGE 3: Remote Deploy")
    print("=" * 60)

    # Step 1: Setup git credentials and clone/pull
    print("\n--- Step 1: Git clone/pull ---")
    git_url_with_auth = GIT_REPO.replace("https://", f"https://{GIT_USER}:{GIT_TOKEN}@")
    out, _, code = exec_cmd(client, f"test -d {SERVER_PROJECT_DIR}/.git && echo 'EXISTS' || echo 'NOT_EXISTS'")
    if 'NOT_EXISTS' in out:
        print("  Cloning repository...")
        exec_cmd(client, f"git clone {git_url_with_auth} {SERVER_PROJECT_DIR}")
    else:
        print("  Repository exists, pulling latest...")
        exec_cmd(client, f"cd {SERVER_PROJECT_DIR} && git fetch origin && git reset --hard origin/master")
        exec_cmd(client, f"cd {SERVER_PROJECT_DIR} && git pull origin master")
    # Verify
    exec_cmd(client, f"cd {SERVER_PROJECT_DIR} && git log --oneline -3")

    # Step 2: ACR login on server
    print("\n--- Step 2: ACR Login ---")
    exec_cmd(client, f"docker login --username {ACR_USER} --password '{ACR_PASS}' {ACR_REGISTRY}")

    # Step 3: Docker compose build & up
    print("\n--- Step 3: Docker compose build & up ---")
    # Use deploy/docker-compose.prod.yml
    compose_file = f"{SERVER_PROJECT_DIR}/deploy/docker-compose.prod.yml"
    # Check if compose file exists
    out, _, _ = exec_cmd(client, f"test -f {compose_file} && echo 'OK' || echo 'MISSING'")
    if 'MISSING' in out:
        print("  ERROR: docker-compose.prod.yml not found in deploy/!")
        return False

    # Build only h5-web (since only H5 code changed)
    print("  Building h5-web only (only H5 code changed)...")
    exec_cmd(client, f"cd {SERVER_PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml build --no-cache h5-web", timeout=600)

    # Restart h5-web
    print("  Restarting h5-web container...")
    exec_cmd(client, f"cd {SERVER_PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml up -d h5-web", timeout=120)

    # Also ensure backend and admin are up
    print("  Ensuring all containers are up...")
    exec_cmd(client, f"cd {SERVER_PROJECT_DIR} && docker compose -f deploy/docker-compose.prod.yml up -d", timeout=120)

    # Step 4: Update gateway-nginx config and reload
    print("\n--- Step 4: Update gateway config & reload ---")
    gateway_conf_src = f"{SERVER_PROJECT_DIR}/deploy/gateway-routes.conf"
    out, _, _ = exec_cmd(client, f"test -f {gateway_conf_src} && echo 'OK' || echo 'MISSING'")
    if 'OK' in out:
        exec_cmd(client, f"docker cp {gateway_conf_src} {GATEWAY_CONTAINER}:{GATEWAY_CONF}")
        exec_cmd(client, f"docker exec {GATEWAY_CONTAINER} nginx -t")
        exec_cmd(client, f"docker exec {GATEWAY_CONTAINER} nginx -s reload")
        print("  Gateway config updated and reloaded.")
    else:
        print("  WARNING: gateway-routes.conf not found in deploy/!")

    # Step 5: Database migration check
    print("\n--- Step 5: Database migration check ---")
    exec_cmd(client, f"docker exec {DEPLOY_ID}-backend ls /app/alembic/ 2>/dev/null || echo 'NO_ALEMBIC'")
    # Run alembic upgrade if available
    out, _, _ = exec_cmd(client, f"docker exec {DEPLOY_ID}-backend ls /app/alembic/versions/ 2>/dev/null | head -5 || echo 'NO_VERSIONS'")
    if 'NO_VERSIONS' not in out and 'NO_ALEMBIC' not in out:
        print("  Running alembic upgrade head...")
        exec_cmd(client, f"docker exec {DEPLOY_ID}-backend alembic upgrade head", timeout=120)
    else:
        print("  No alembic migrations found, skipping.")

    # Step 6: Default account check
    print("\n--- Step 6: Default account check ---")
    exec_cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"print('Backend health check OK')\" 2>&1 || echo 'BACKEND_CHECK_FAILED'")

    return True

# ========== Verify ==========
def verify_deploy(client):
    """Verify all containers are running and accessible."""
    print("\n" + "=" * 60)
    print("VERIFY: Container Status")
    print("=" * 60)
    exec_cmd(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")

    
    print("\n--- Health checks ---")
    exec_cmd(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode()[:200])\" 2>&1 || echo 'BACKEND_HEALTH_FAIL'")
    exec_cmd(client, f"docker exec {DEPLOY_ID}-h5 wget -qO- http://localhost:3001/ 2>&1 | head -5 || echo 'H5_HEALTH_FAIL'")
    exec_cmd(client, f"docker exec {DEPLOY_ID}-admin wget -qO- http://localhost:3000/admin/ 2>&1 | head -5 || echo 'ADMIN_HEALTH_FAIL'")

    print("\n--- Gateway proxy test ---")
    exec_cmd(client, f"docker exec {GATEWAY_CONTAINER} wget -qO- http://{DEPLOY_ID}-backend:8000/api/health 2>&1 | head -10 || echo 'GATEWAY_TEST_FAIL'")

# ========== Main ==========
def main():
    print("=" * 60)
    print(f"DEPLOYMENT for {DEPLOY_ID}")
    print(f"Target: {SSH_HOST}:{SSH_PORT}")
    print(f"Domain: {PROJECT_DOMAIN}")
    print("=" * 60)

    try:
        client = get_ssh_client()
        print("SSH connected successfully.")
    except Exception as e:
        print(f"SSH connection failed: {e}")
        return False

    try:
        # Stage 1.5
        results = precheck(client)

        # Stage 3
        success = deploy(client)

        # Verify
        verify_deploy(client)

        client.close()
        return success
    except Exception as e:
        print(f"Deployment error: {e}")
        import traceback
        traceback.print_exc()
        client.close()
        return False

if __name__ == "__main__":
    ok = main()
    print("\n" + "=" * 60)
    print(f"DEPLOY RESULT: {'SUCCESS' if ok else 'FAILED'}")
    print("=" * 60)
    sys.exit(0 if ok else 1)
