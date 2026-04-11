import paramiko
import time
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PROJECT_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

def run_ssh_command(ssh, cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT CODE] {exit_code}")
    return exit_code, out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    print("Connected to server.")

    # Check backend logs
    print("\n=== Backend container logs (last 30 lines) ===")
    run_ssh_command(ssh, "docker logs --tail 30 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend")

    # Check h5 logs
    print("\n=== H5 container logs (last 30 lines) ===")
    run_ssh_command(ssh, "docker logs --tail 30 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-h5")

    # Check the gateway nginx config for this project
    print("\n=== Gateway nginx config for this project ===")
    run_ssh_command(ssh, "docker exec gateway-nginx cat /etc/nginx/conf.d/3b7b999d-e51c-4c0d-8f6e-baf90cd26857.conf 2>/dev/null || echo 'No config found in gateway-nginx'")
    run_ssh_command(ssh, "docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null || echo 'gateway-nginx container not found'")

    # Check if gateway-nginx can reach the backend container
    print("\n=== Network connectivity check ===")
    run_ssh_command(ssh, "docker network ls | grep -i 3b7b999d")
    run_ssh_command(ssh, f"docker inspect --format='{{{{.NetworkSettings.Networks}}}}' 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend")
    run_ssh_command(ssh, f"docker inspect --format='{{{{.NetworkSettings.Networks}}}}' gateway-nginx 2>/dev/null || echo 'gateway-nginx not found'")

    # Try direct curl to backend from within server  
    print("\n=== Direct curl to backend container ===")
    run_ssh_command(ssh, "docker exec 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend curl -s http://localhost:8000/api/home-config 2>/dev/null || echo 'curl not available in container'")
    
    # Try via docker network
    run_ssh_command(ssh, "docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend")

    # Wait and retry health checks
    print("\n=== Waiting 15 more seconds and retrying health checks ===")
    time.sleep(15)
    
    _, api_response, _ = run_ssh_command(ssh, f"curl -s {BASE_URL}/api/home-config")
    _, h5_status, _ = run_ssh_command(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/")

    print(f"\nAPI response: {api_response.strip()[:500]}")
    print(f"H5 status: {h5_status.strip()}")

    ssh.close()

if __name__ == "__main__":
    main()
