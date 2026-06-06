#!/usr/bin/env python3
"""Phase 1.5: Server environment precheck (6 items) via SSH."""
import paramiko
import json
import sys

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
GATEWAY_CONTAINER = "gateway-nginx"
ACR_BASE = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base"


def ssh_exec(ssh, cmd, timeout=30):
    """Execute SSH command and return stdout, stderr, exit_code."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code


def main():
    print("=" * 60)
    print("Phase 1.5: Server Environment Precheck")
    print("=" * 60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
        print("[OK] SSH connection established")
    except Exception as e:
        print(f"[FAIL] SSH connection failed: {e}")
        sys.exit(1)

    results = {}

    # === Check 1: Gateway nginx config structure ===
    print("\n--- Check 1: Gateway nginx config structure ---")
    out, err, ec = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} ls -la /etc/nginx/conf.d/ 2>/dev/null || echo 'CONTAINER_NOT_FOUND'")
    print(f"  conf.d listing: {out[:500]}")
    out2, err2, ec2 = ssh_exec(ssh, f"docker exec {GATEWAY_CONTAINER} cat /etc/nginx/nginx.conf 2>/dev/null | head -60 || echo 'NO_NGINX_CONF'")
    print(f"  main nginx.conf head: {out2[:300]}")
    results['gateway_structure'] = 'ok' if 'CONTAINER_NOT_FOUND' not in out else 'container_missing'

    # === Check 2: Route occupation ===
    print("\n--- Check 2: Route occupation check ---")
    out, err, ec = ssh_exec(ssh, f"test -f {GATEWAY_CONF} && echo 'EXISTS' || echo 'NOT_FOUND'")
    print(f"  Gateway conf {GATEWAY_CONF}: {out}")
    # Check if port 8000/3000/3001 are in use
    out, err, ec = ssh_exec(ssh, "ss -tlnp 2>/dev/null | grep -E ':(8000|3000|3001) ' || echo 'NO_PORTS_IN_USE'")
    print(f"  Port occupation: {out[:300]}")
    results['route_occupation'] = out

    # === Check 3: ACR base image versions ===
    print("\n--- Check 3: ACR base image version matching ---")
    out, err, ec = ssh_exec(ssh, "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep 'noob_doker_base' | head -10 || echo 'NO_ACR_IMAGES'")
    print(f"  ACR base images on server: {out[:400]}")
    results['acr_images'] = out if out else 'none'

    # === Check 4: Docker network topology ===
    print("\n--- Check 4: Docker network topology ---")
    out, err, ec = ssh_exec(ssh, f"docker network ls --format '{{.Name}}' 2>/dev/null")
    print(f"  Networks: {out[:400]}")
    # Check if project network exists
    net_name = f"{DEPLOY_ID}-network"
    out2, err2, ec2 = ssh_exec(ssh, f"docker network inspect {net_name} 2>/dev/null | head -30 || echo 'NETWORK_NOT_FOUND'")
    print(f"  Project network ({net_name}): {out2[:300]}")
    # Check gateway network connection
    out3, err3, ec3 = ssh_exec(ssh, f"docker inspect {GATEWAY_CONTAINER} --format '{{{{.NetworkSettings.Networks}}}}' 2>/dev/null | head -20 || echo 'GATEWAY_NOT_FOUND'")
    print(f"  Gateway networks: {out3[:300]}")
    results['docker_network'] = 'ok' if 'NETWORK_NOT_FOUND' not in out2 else 'network_missing'

    # === Check 5: Base image built-in tools ===
    print("\n--- Check 5: Base image built-in tools detection ---")
    for img_tag in ['python:3.12-slim', 'node:20-alpine']:
        img = f"{ACR_BASE}/{img_tag}"
        out, err, ec = ssh_exec(ssh, f"docker run --rm {img} sh -c 'echo Python:$(python3 --version 2>/dev/null||echo NA); echo Pip:$(pip --version 2>/dev/null||echo NA)' 2>/dev/null || echo 'IMAGE_NOT_FOUND_OR_PULL_FAILED'")
        print(f"  {img}: {out[:200]}")
    results['base_tools'] = 'checked'

    # === Check 6: Disk space ===
    print("\n--- Check 6: Disk space check ---")
    out, err, ec = ssh_exec(ssh, "df -h / 2>/dev/null")
    print(f"  Disk: {out}")
    out2, err2, ec2 = ssh_exec(ssh, "df -h /home 2>/dev/null")
    print(f"  /home: {out2}")
    results['disk_space'] = out

    # Summary
    print("\n" + "=" * 60)
    print("Precheck Summary:")
    for k, v in results.items():
        print(f"  {k}: {str(v)[:100]}")
    print("=" * 60)

    ssh.close()
    return results


if __name__ == "__main__":
    main()
