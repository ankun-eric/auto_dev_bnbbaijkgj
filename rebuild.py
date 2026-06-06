"""
Rebuild backend and h5-web containers on remote server.
"""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def ssh_exec(client, command, timeout=300):
    """Execute command and return (exit_code, stdout, stderr)"""
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, out, err

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    
    # Step 1: Get BUILD_COMMIT
    cmd = "cd {} && git log -1 --format=%H".format(DEPLOY_DIR)
    code, out, err = ssh_exec(client, cmd, 15)
    build_commit = out.strip()
    print(f"BUILD_COMMIT: {build_commit}")
    
    # Step 2: Rebuild backend
    print("\n=== Rebuilding backend ===")
    cmd = "cd {} && BUILD_COMMIT={} docker compose -f docker-compose.prod.yml build --pull backend 2>&1".format(
        DEPLOY_DIR, build_commit)
    code, out, err = ssh_exec(client, cmd, 600)
    print(out[-3000:] if len(out) > 3000 else out)
    if code != 0:
        print(f"Backend build error: {err[-2000:]}")
        # Try without --pull
        print("\n=== Retrying backend build without --pull ===")
        cmd = "cd {} && BUILD_COMMIT={} docker compose -f docker-compose.prod.yml build backend 2>&1".format(
            DEPLOY_DIR, build_commit)
        code, out, err = ssh_exec(client, cmd, 600)
        print(out[-3000:] if len(out) > 3000 else out)
    
    # Step 3: Rebuild h5-web
    print("\n=== Rebuilding h5-web ===")
    cmd = "cd {} && BUILD_COMMIT={} docker compose -f docker-compose.prod.yml build --pull h5-web 2>&1".format(
        DEPLOY_DIR, build_commit)
    code, out, err = ssh_exec(client, cmd, 600)
    print(out[-3000:] if len(out) > 3000 else out)
    if code != 0:
        print(f"H5 build error: {err[-2000:]}")
        print("\n=== Retrying h5 build without --pull ===")
        cmd = "cd {} && BUILD_COMMIT={} docker compose -f docker-compose.prod.yml build h5-web 2>&1".format(
            DEPLOY_DIR, build_commit)
        code, out, err = ssh_exec(client, cmd, 600)
        print(out[-3000:] if len(out) > 3000 else out)
    
    # Step 4: Restart containers
    print("\n=== Restarting containers ===")
    cmd = "cd {} && docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1".format(DEPLOY_DIR)
    code, out, err = ssh_exec(client, cmd, 60)
    print(out)
    if err:
        print(f"Stderr: {err[-500:]}")
    
    # Step 5: Wait for health checks
    print("\n=== Waiting for health checks ===")
    max_wait = 24
    for i in range(max_wait):
        time.sleep(5)
        cmd = "cd {} && docker compose -f docker-compose.prod.yml ps --format json 2>&1".format(DEPLOY_DIR)
        code, out, err = ssh_exec(client, cmd, 10)
        print(f"  [{i+1}/{max_wait}] Status check...")
        if out:
            lines = out.strip().split('\n')
            healthy_count = sum(1 for l in lines if '"Health":"healthy"' in l)
            total = len(lines)
            print(f"    {healthy_count}/{total} healthy")
            if healthy_count == total:
                print("All containers healthy!")
                break
    else:
        print("Timeout waiting for health checks")
    
    # Step 6: Ensure gateway connected to network
    print("\n=== Ensuring gateway network connection ===")
    cmd = "docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway-nginx 2>&1 || true"
    code, out, err = ssh_exec(client, cmd, 10)
    print(out)
    
    # Step 7: Reload gateway
    print("\n=== Reloading gateway ===")
    cmd = "docker exec gateway-nginx nginx -t 2>&1 && docker exec gateway-nginx nginx -s reload 2>&1"
    code, out, err = ssh_exec(client, cmd, 15)
    print(out)
    if err:
        print(f"Gateway error: {err}")
    
    # Step 8: Verify BUILD_INFO
    print("\n=== Verifying BUILD_INFO ===")
    cmd = "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend cat /app/BUILD_INFO 2>&1"
    code, out, err = ssh_exec(client, cmd, 10)
    print(f"Backend BUILD_INFO: {out.strip()}")
    print(f"Expected: {build_commit}")
    print(f"Match: {out.strip() == build_commit}")
    
    client.close()
    print("\n=== Deployment complete ===")

if __name__ == "__main__":
    main()
