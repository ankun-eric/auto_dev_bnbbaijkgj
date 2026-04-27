import paramiko
import time
import sys

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def run_ssh(client, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT CODE] {exit_code}")
    return exit_code, out, err

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {SSH_HOST}...")
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    print("Connected.")

    # Step 1: Pull latest code
    print("\n=== STEP 1: Pull latest code ===")
    code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master && git clean -fd && git log -1 --oneline")
    if code != 0:
        print("Git pull failed, trying with token URL...")
        run_ssh(client, f"cd {PROJECT_DIR} && git remote set-url origin https://ankun-eric:{{GH_TOKEN}}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git")
        code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master && git clean -fd && git log -1 --oneline")
        if code != 0:
            print("FATAL: Git pull failed even with token.")
            sys.exit(1)

    # Step 2: Rebuild containers
    print("\n=== STEP 2: Rebuild and restart containers ===")
    compose_cmd = "docker compose"
    code, _, _ = run_ssh(client, f"docker compose version")
    if code != 0:
        compose_cmd = "docker-compose"
        print("Using docker-compose (v1)")

    code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml build --no-cache backend", timeout=300)
    if code != 0:
        print("WARNING: Backend build failed!")
        print(err)

    code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml build --no-cache frontend", timeout=300)
    if code != 0:
        print("WARNING: Frontend build failed!")
        print(err)

    code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml up -d", timeout=120)
    if code != 0:
        print("WARNING: docker compose up failed!")

    # Step 3: Wait for health checks
    print("\n=== STEP 3: Wait for containers to be healthy ===")
    for i in range(24):
        time.sleep(5)
        code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml ps")
        if "unhealthy" not in out and ("healthy" in out or i >= 12):
            print("Containers appear ready.")
            break
        print(f"Waiting... ({(i+1)*5}s)")
    else:
        print("WARNING: Health check timeout after 120s, continuing anyway...")

    # Step 4: Reconnect gateway network + reload
    print("\n=== STEP 4: Reconnect gateway network & reload nginx ===")
    run_ssh(client, "docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway 2>/dev/null || true")
    run_ssh(client, "docker exec gateway nginx -s reload")

    # Step 5: Final container status
    print("\n=== STEP 5: Final container status ===")
    run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml ps")
    run_ssh(client, "docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}' | grep -E '6b099ed3|gateway'")

    client.close()
    print("\n=== SSH deployment complete ===")

if __name__ == "__main__":
    main()
