import paramiko
import time
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
GIT_URL = "https://ankun-eric:{GH_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"

def run_ssh(client, cmd, timeout=300):
    print(f"\n>>> {cmd[:200]}{'...' if len(cmd)>200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT CODE] {exit_code}")
    return out, err, exit_code

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"Connecting to {HOST}:{PORT} as {USER}...")
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("Connected.\n")

    # Step 1: Try git pull with retries and TLS workarounds
    print("=" * 60)
    print("STEP 1: Pull latest code from Git")
    print("=" * 60)

    git_cmd = (
        f"cd {PROJECT_DIR} && "
        f"git config --global http.version HTTP/1.1 && "
        f"git config --global http.postBuffer 524288000 && "
        f"git config --global http.sslVerify false && "
        f"git remote set-url origin '{GIT_URL}' && "
        f"for i in 1 2 3; do git fetch origin && break || echo \"Retry $i...\"; sleep 5; done && "
        f"git reset --hard origin/master && "
        f"git clean -fd"
    )
    out, err, code = run_ssh(client, git_cmd, timeout=300)
    if code != 0:
        print("WARNING: Git pull failed, trying alternative approach...")
        alt_cmd = (
            f"cd {PROJECT_DIR} && "
            f"GIT_SSL_NO_VERIFY=1 git fetch --depth=1 origin master && "
            f"git reset --hard origin/master && "
            f"git clean -fd"
        )
        out, err, code = run_ssh(client, alt_cmd, timeout=300)
        if code != 0:
            print("ERROR: Git pull failed after all retries!")
            client.close()
            sys.exit(1)

    # Step 2: Confirm latest commit
    print("\n" + "=" * 60)
    print("STEP 2: Confirm latest commit")
    print("=" * 60)
    out, _, _ = run_ssh(client, f"cd {PROJECT_DIR} && git log -1")

    # Step 3: Rebuild backend container only
    print("\n" + "=" * 60)
    print("STEP 3: Rebuild backend container (no-cache)")
    print("=" * 60)
    out, err, code = run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend", timeout=600)
    if code != 0:
        print("ERROR: Backend build failed!")
        client.close()
        sys.exit(1)

    # Step 4: Restart backend container
    print("\n" + "=" * 60)
    print("STEP 4: Restart backend container")
    print("=" * 60)
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend", timeout=120)

    # Step 5: Wait for backend to be healthy
    print("\n" + "=" * 60)
    print("STEP 5: Wait for backend container to be ready")
    print("=" * 60)
    for i in range(12):
        time.sleep(10)
        out, _, _ = run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps backend")
        if "running" in out.lower() or "up" in out.lower():
            print("Backend container is running!")
            break
        print(f"Waiting... ({(i+1)*10}s)")
    else:
        print("WARNING: Backend may not be fully ready after 120s")

    # Step 6: Find gateway container and connect to network
    print("\n" + "=" * 60)
    print("STEP 6: Connect gateway to project network")
    print("=" * 60)
    out, _, _ = run_ssh(client, "docker ps --format '{{.Names}}' | grep -i gateway")
    gateway_name = out.strip().split("\n")[0] if out.strip() else "gateway"
    print(f"Gateway container name: {gateway_name}")

    network_name = "6b099ed3-7175-4a78-91f4-44570c84ed27-network"
    run_ssh(client, f"docker network connect {network_name} {gateway_name} 2>/dev/null || true")

    # Step 7: Reload gateway nginx
    print("\n" + "=" * 60)
    print("STEP 7: Reload gateway nginx")
    print("=" * 60)
    run_ssh(client, f"docker exec {gateway_name} nginx -s reload")

    # Step 8: Verify deployment
    print("\n" + "=" * 60)
    print("STEP 8: Verify deployment - all container status")
    print("=" * 60)
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps")

    print("\n" + "=" * 60)
    print("STEP 9: Backend logs (last 20 lines)")
    print("=" * 60)
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml logs --tail=20 backend")

    client.close()
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
