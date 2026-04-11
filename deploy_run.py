import paramiko
import sys
import time

HOST = "newbb.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PORT = 22
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_TAR = r"C:\auto_output\bnbbaijkgj\deploy_package.tar.gz"

def ssh_exec(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"STDERR: {err.strip()}")
    print(f"[exit_code={exit_code}]")
    return exit_code, out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("=== Step 1: SSH connect ===")
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("SSH connected OK")

    print("\n=== Step 2: Upload deploy_package.tar.gz ===")
    sftp = ssh.open_sftp()
    remote_tar = f"{REMOTE_DIR}/deploy_package.tar.gz"
    sftp.put(LOCAL_TAR, remote_tar, callback=lambda sent, total: None)
    stat = sftp.stat(remote_tar)
    print(f"Uploaded: {stat.st_size} bytes")
    sftp.close()

    print("\n=== Step 3: Extract and rebuild ===")
    ssh_exec(ssh, f"cd {REMOTE_DIR} && tar xzf deploy_package.tar.gz")
    ssh_exec(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend admin-web", timeout=600)
    ssh_exec(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend admin-web", timeout=120)

    print("\n=== Step 4: Wait for containers to start ===")
    time.sleep(12)

    print("\n=== Step 5: Container status ===")
    ssh_exec(ssh, f"docker compose -f {REMOTE_DIR}/docker-compose.prod.yml ps")

    print("\n=== Step 6: Gateway network ===")
    ssh_exec(ssh, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || echo 'Already connected or not needed'")

    print("\n=== Step 7: Reload gateway ===")
    ssh_exec(ssh, "docker exec gateway-nginx nginx -s reload 2>/dev/null || echo 'Gateway reload skipped'")

    print("\n=== Step 8: Verify deployment ===")
    ssh_exec(ssh, f'docker ps --filter "name={DEPLOY_ID}" --format "table {{{{.Names}}}}\\t{{{{.Status}}}}"')
    ssh_exec(ssh, f"curl -s http://localhost:8000/api/health 2>/dev/null || curl -s http://{DEPLOY_ID}-backend:8000/api/health 2>/dev/null || echo 'Direct health check not available'")
    ssh_exec(ssh, f"curl -sk https://newbb.bangbangvip.com/autodev/{DEPLOY_ID}/api/health")
    exit_code, out, _ = ssh_exec(ssh, f"curl -sI https://newbb.bangbangvip.com/autodev/{DEPLOY_ID}/admin/ | head -5")

    print("\n=== Step 9: Container logs (last 20 lines) ===")
    ssh_exec(ssh, f"docker logs --tail 20 {DEPLOY_ID}-backend 2>&1")
    ssh_exec(ssh, f"docker logs --tail 10 {DEPLOY_ID}-admin 2>&1")

    ssh.close()
    print("\n=== Deployment complete ===")

if __name__ == "__main__":
    main()
