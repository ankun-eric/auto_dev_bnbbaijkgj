import paramiko
import json
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Bangbang987", timeout=30)

deploy_id = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

# Remove the failed container first
stdin, stdout, stderr = ssh.exec_command("docker rm -f gateway-nginx 2>/dev/null")
stdout.channel.recv_exit_status()
print("Removed old container")

# List available docker networks
stdin, stdout, stderr = ssh.exec_command("docker network ls --format '{{.Name}}'")
networks = stdout.read().decode().strip().split("\n")
print(f"Available networks: {networks}")

# Find the project networks
project_networks = [n for n in networks if deploy_id in n or "5cffe06b" in n]
print(f"Project networks: {project_networks}")

# Build docker run command with correct network names
network_args = ""
first_network = None
extra_networks = []
for n in project_networks:
    if first_network is None:
        first_network = n
    else:
        extra_networks.append(n)

run_cmd = (
    f"docker run -d --name gateway-nginx "
    f"{'--network ' + first_network if first_network else ''} "
    f"-p 80:80 -p 443:443 "
    f"-v /home/ubuntu/gateway/nginx.conf:/etc/nginx/nginx.conf:ro "
    f"-v /home/ubuntu/gateway/ssl:/etc/nginx/ssl:ro "
    f"-v /home/ubuntu/gateway/conf.d:/etc/nginx/conf.d:ro "
    f"-v /home/ubuntu/gateway/certbot-webroot:/var/www/certbot:ro "
    f"-v /home/ubuntu/{deploy_id}/static:/home/ubuntu/{deploy_id}/static:ro "
    f"-v /home/ubuntu/{deploy_id}:/home/ubuntu/{deploy_id}:ro "
    f"--restart unless-stopped "
    f"nginx:latest"
)

print(f"\n>>> {run_cmd}")
stdin, stdout, stderr = ssh.exec_command(run_cmd)
exit_status = stdout.channel.recv_exit_status()
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
print(f"OUT: {out}")
if err:
    print(f"ERR: {err}")
print(f"Exit: {exit_status}")

# Connect to additional networks
for n in extra_networks:
    cmd = f"docker network connect {n} gateway-nginx"
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"OUT: {out}")
    if err:
        print(f"ERR: {err}")
    print(f"Exit: {exit_status}")

time.sleep(3)

# Verify
stdin, stdout, stderr = ssh.exec_command("docker ps --filter name=gateway-nginx --format '{{.Status}}'")
status = stdout.read().decode().strip()
print(f"\nGateway status: {status}")

stdin, stdout, stderr = ssh.exec_command("docker exec gateway-nginx nginx -t 2>&1")
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
print(f"Nginx test: {out} {err}")

ssh.close()
