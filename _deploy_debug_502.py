"""Debug 502 error: check container logs, nginx config, and internal connectivity."""
import paramiko
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"
PROJECT_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def ssh_exec(ssh, cmd, timeout=60):
    print(f"\n[SSH] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    combined = out + err
    if combined.strip():
        print(combined.strip()[:3000])
    return exit_code, out.strip(), err.strip()


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    print("Connected!")

    # 1. Check backend logs
    print("\n===== BACKEND CONTAINER LOGS (last 30 lines) =====")
    ssh_exec(ssh, f"docker logs --tail 30 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend")

    # 2. Check h5 logs
    print("\n===== H5 CONTAINER LOGS (last 30 lines) =====")
    ssh_exec(ssh, f"docker logs --tail 30 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-h5")

    # 3. Check docker-compose ports
    print("\n===== DOCKER COMPOSE CONFIG =====")
    ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps")

    # 4. Check container network
    print("\n===== CONTAINER NETWORK =====")
    ssh_exec(ssh, "docker network ls | grep 3b7b999d")

    # 5. Check gateway nginx config for this project
    print("\n===== GATEWAY NGINX CONFIG =====")
    ssh_exec(ssh, "docker exec gateway-nginx cat /etc/nginx/conf.d/autodev_3b7b999d.conf 2>/dev/null || echo 'Config not found, checking alternatives...'")
    ssh_exec(ssh, "docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null | grep -i 3b7b999d")
    ssh_exec(ssh, "docker exec gateway-nginx grep -r '3b7b999d' /etc/nginx/conf.d/ 2>/dev/null | head -20")

    # 6. Check if there's a general autodev config
    print("\n===== ALL NGINX CONF FILES =====")
    ssh_exec(ssh, "docker exec gateway-nginx ls /etc/nginx/conf.d/")

    # 7. Test internal connectivity
    print("\n===== INTERNAL CONNECTIVITY TEST =====")
    ssh_exec(ssh, "docker exec gateway-nginx curl -s -o /dev/null -w '%{http_code}' http://3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend:8000/api/home-config 2>/dev/null || echo 'Cannot curl internally from gateway'")

    # 8. Check if containers are on same network as gateway
    print("\n===== GATEWAY NETWORK =====")
    ssh_exec(ssh, "docker inspect gateway-nginx --format='{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null")
    ssh_exec(ssh, "docker inspect 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend --format='{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null")

    # 9. Check docker-compose.prod.yml for network config
    print("\n===== DOCKER-COMPOSE PROD NETWORK CONFIG =====")
    ssh_exec(ssh, f"cd {PROJECT_DIR} && cat docker-compose.prod.yml")

    ssh.close()


if __name__ == "__main__":
    main()
