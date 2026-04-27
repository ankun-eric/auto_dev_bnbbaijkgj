import paramiko
import time

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

    compose_cmd = "docker compose"

    # Rebuild admin-web
    print("\n=== Rebuild admin-web ===")
    code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml build --no-cache admin-web", timeout=300)
    if code != 0:
        print(f"admin-web build failed!")

    # Rebuild h5-web
    print("\n=== Rebuild h5-web ===")
    code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml build --no-cache h5-web", timeout=300)
    if code != 0:
        print(f"h5-web build failed!")

    # Restart all
    print("\n=== Restart all containers ===")
    code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml up -d", timeout=120)

    # Wait for health
    print("\n=== Wait for containers ===")
    for i in range(24):
        time.sleep(5)
        code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml ps")
        if "unhealthy" not in out and ("healthy" in out or i >= 6):
            print("Containers appear ready.")
            break
        print(f"Waiting... ({(i+1)*5}s)")

    # Reconnect gateway
    print("\n=== Reconnect gateway ===")
    run_ssh(client, "docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway 2>/dev/null || true")
    run_ssh(client, "docker exec gateway nginx -s reload")

    # Final status
    print("\n=== Final container status ===")
    run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml ps")

    client.close()
    print("\n=== Frontend rebuild complete ===")

if __name__ == "__main__":
    main()
