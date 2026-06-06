"""Server environment pre-check script for deployment."""
import paramiko
import sys
import json

HOST = "134.175.97.26"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_doker_base"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

def ssh_cmd(ssh, cmd, timeout=30):
    """Execute command via SSH and return stdout, stderr, exit_code."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
        print("=== SSH Connected ===")
    except Exception as e:
        print(f"SSH FAILED: {e}")
        sys.exit(1)

    results = {}

    # ── Pre-check 1: Gateway nginx structure ──
    print("\n--- 1. Gateway nginx.conf structure ---")
    out, err, code = ssh_cmd(ssh, "cat /home/ubuntu/gateway/nginx.conf 2>/dev/null || echo 'NOT_FOUND'")
    results['gateway_nginx'] = out[:3000] if len(out) > 3000 else out
    print(f"exit={code}, len={len(out)}")
    if out:
        # Show first 500 chars
        print(out[:500])

    # ── Pre-check 2: Route conflicts ──
    print("\n--- 2. Route conflicts check ---")
    out, err, code = ssh_cmd(ssh, "grep -rn 'location\\|server_name' /home/ubuntu/gateway/conf.d/ 2>/dev/null || echo 'EMPTY'")
    results['route_conflicts'] = out[:2000]
    print(out[:500])
    
    out2, err2, code2 = ssh_cmd(ssh, "grep -n 'location\\|server_name' /home/ubuntu/gateway/nginx.conf 2>/dev/null | head -30")
    results['nginx_locations'] = out2[:2000]
    print(out2[:500])

    # ── Pre-check 3: ACR image versions ──
    print("\n--- 3. ACR image versions ---")
    # Quick check via docker manifest inspect on server
    acr_check_cmd = """
for img in python node; do
  case $img in
    python) tags="3.12-slim 3.11-slim 3.10-slim 3.12 3.11" ;;
    node)   tags="22-alpine 20-alpine 18-alpine 22 20 18" ;;
  esac
  for tag in $tags; do
    result=$(docker manifest inspect {ACR}/{NS}/$img:$tag 2>&1)
    if [ $? -eq 0 ]; then
      echo "FOUND: {ACR}/{NS}/$img:$tag"
    fi
  done
done
""".format(ACR=ACR_ADDR, NS=ACR_NS)
    out, err, code = ssh_cmd(ssh, acr_check_cmd, timeout=45)
    results['acr_versions'] = out[:2000]
    print(out[:500])

    # ── Pre-check 4: Docker network topology ──
    print("\n--- 4. Docker network topology ---")
    out, err, code = ssh_cmd(ssh, "docker ps -a --filter name=gateway-nginx --format '{{.Names}} {{.Status}}' 2>/dev/null || echo 'NOT_FOUND'")
    results['gateway_status'] = out
    print(f"gateway-nginx: {out}")
    
    out2, err2, code2 = ssh_cmd(ssh, "docker inspect gateway-nginx --format '{{range .NetworkSettings.Networks}}{{.Name}} {{end}}' 2>/dev/null || echo 'NO_NETWORKS'")
    results['gateway_networks'] = out2
    print(f"gateway networks: {out2}")
    
    out3, err3, code3 = ssh_cmd(ssh, f"docker network ls --filter name={DEPLOY_ID}-network --format '{{{{.Name}}}}' 2>/dev/null || echo 'NOT_FOUND'")
    results['deploy_network'] = out3
    print(f"{DEPLOY_ID}-network: {out3}")
    
    out4, err4, code4 = ssh_cmd(ssh, f"docker ps -a --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}' 2>/dev/null || echo 'NONE'")
    results['existing_containers'] = out4
    print(f"existing containers: {out4}")

    # ── Pre-check 5: Image tool detection ──
    print("\n--- 5. Image tool detection ---")
    py_img = f"{ACR_ADDR}/{ACR_NS}/python:3.12-slim"
    out, err, code = ssh_cmd(ssh, f"docker run --rm {py_img} sh -c 'which wget curl python3 2>/dev/null' 2>&1", timeout=60)
    results['python_tools'] = out
    print(f"python: {out}")
    
    node_img = f"{ACR_ADDR}/{ACR_NS}/node:20-alpine"
    out2, err2, code2 = ssh_cmd(ssh, f"docker run --rm {node_img} sh -c 'which wget curl node 2>/dev/null' 2>&1", timeout=60)
    results['node_tools'] = out2
    print(f"node: {out2}")

    # ── Pre-check 6: Disk space ──
    print("\n--- 6. Disk space ---")
    out, err, code = ssh_cmd(ssh, "df -h / | tail -1")
    results['disk_space'] = out
    print(f"disk: {out}")

    # Also check DB container
    print("\n--- Extra: DB container check ---")
    out, err, code = ssh_cmd(ssh, "docker ps -a --filter name=db --format '{{.Names}} {{.Status}} {{.Ports}}' 2>/dev/null || echo 'NO_DB'")
    results['db_container'] = out
    print(f"db: {out}")

    # Check which networks db is on
    out2, err2, code2 = ssh_cmd(ssh, "docker inspect db --format '{{range .NetworkSettings.Networks}}{{.Name}} {{end}}' 2>/dev/null || echo 'NO_DB_NET'")
    results['db_networks'] = out2
    print(f"db networks: {out2}")

    ssh.close()
    
    # Print summary JSON
    print("\n\n===== RESULTS JSON =====")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
