"""Deploy script using paramiko for SSH/SFTP operations."""
import paramiko
import os
import sys
import time
import stat

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", "venv", ".venv",
    "mysql_data", "uploads_data", ".chat_attachments", "deploy", "docs",
    "mem", "agent-transcripts", ".tools", ".cursor", "terminals",
}
EXCLUDE_FILES = {".env.local"}


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run_cmd(ssh, cmd, timeout=600):
    print(f"  CMD: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(f"  STDOUT: {out.strip()[:2000]}")
    if err.strip():
        print(f"  STDERR: {err.strip()[:2000]}")
    print(f"  EXIT: {exit_code}")
    return exit_code, out, err


def upload_dir(sftp, local_path, remote_path):
    """Recursively upload a directory."""
    for item in os.listdir(local_path):
        if item in EXCLUDE_DIRS or item in EXCLUDE_FILES:
            continue
        local_item = os.path.join(local_path, item)
        remote_item = remote_path + "/" + item
        if os.path.isdir(local_item):
            try:
                sftp.stat(remote_item)
            except FileNotFoundError:
                sftp.mkdir(remote_item)
            upload_dir(sftp, local_item, remote_item)
        else:
            if os.path.getsize(local_item) > 50 * 1024 * 1024:
                print(f"  SKIP large file: {item}")
                continue
            print(f"  UPLOAD: {item}")
            sftp.put(local_item, remote_item)


def main():
    print("=" * 60)
    print("STEP 1: Upload code to server")
    print("=" * 60)
    ssh = get_ssh()
    run_cmd(ssh, f"mkdir -p {REMOTE_DIR}")
    sftp = ssh.open_sftp()
    upload_dir(sftp, LOCAL_DIR, REMOTE_DIR)
    sftp.close()
    print("Upload complete.\n")

    print("=" * 60)
    print("STEP 2: Build and start Docker containers")
    print("=" * 60)
    exit_code, out, err = run_cmd(
        ssh,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d --build 2>&1",
        timeout=600,
    )
    if exit_code != 0:
        print("ERROR: Docker build failed!")
        ssh.close()
        sys.exit(1)
    print("Docker build complete.\n")

    print("Waiting 15s for containers to start...")
    time.sleep(15)

    print("=" * 60)
    print("STEP 2b: Check container status")
    print("=" * 60)
    run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1")

    print("\n" + "=" * 60)
    print("STEP 3: Check and configure gateway nginx")
    print("=" * 60)
    check_and_configure_nginx(ssh)

    print("\n" + "=" * 60)
    print("STEP 4: Verify links")
    print("=" * 60)
    verify_links(ssh)

    ssh.close()
    print("\nDeployment script finished.")


def check_and_configure_nginx(ssh):
    uid = "6b099ed3-7175-4a78-91f4-44570c84ed27"
    prefix = f"6b099ed3-7175-4a78-91f4-44570c84ed27"

    # Check if gateway-nginx exists
    exit_code, out, _ = run_cmd(ssh, "ls /home/ubuntu/gateway-nginx/")
    if exit_code != 0:
        exit_code, out, _ = run_cmd(ssh, "ls /etc/nginx/")

    # Check if config already exists for this project
    exit_code, out, _ = run_cmd(ssh, f"grep -r '{uid}' /home/ubuntu/gateway-nginx/ 2>/dev/null || grep -r '{uid}' /etc/nginx/conf.d/ 2>/dev/null || grep -r '{uid}' /etc/nginx/sites-enabled/ 2>/dev/null || echo 'NOT_FOUND'")

    if "NOT_FOUND" in out:
        print("  Nginx config not found, need to add it.")
        add_nginx_config(ssh, uid, prefix)
    else:
        print("  Nginx config already exists for this project.")
        # Still update it to make sure it's current
        print("  Updating nginx config to ensure it's current...")
        add_nginx_config(ssh, uid, prefix)

    # Ensure project containers are on the gateway network
    ensure_network(ssh, uid, prefix)


def add_nginx_config(ssh, uid, prefix):
    conf_content = f"""
# Auto-generated config for {uid}
location /autodev/{uid}/ {{
    proxy_pass http://{prefix}-h5:3001/autodev/{uid}/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}}

location /autodev/{uid}/admin/ {{
    proxy_pass http://{prefix}-admin:3000/autodev/{uid}/admin/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}}

location /autodev/{uid}/api/ {{
    proxy_pass http://{prefix}-backend:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}}
"""
    # Escape for shell
    escaped = conf_content.replace("'", "'\\''")
    
    # Try gateway-nginx directory first
    exit_code, out, _ = run_cmd(ssh, "ls /home/ubuntu/gateway-nginx/conf.d/ 2>/dev/null && echo EXISTS || echo NODIR")
    if "EXISTS" in out:
        conf_path = f"/home/ubuntu/gateway-nginx/conf.d/{uid}.conf"
        run_cmd(ssh, f"cat > {conf_path} << 'CONFEOF'\n{conf_content}\nCONFEOF")
        # Reload gateway nginx
        run_cmd(ssh, "docker exec gateway-nginx nginx -t 2>&1 && docker exec gateway-nginx nginx -s reload 2>&1")
    else:
        # Check for locations.d or similar include pattern
        exit_code, out, _ = run_cmd(ssh, "ls /home/ubuntu/gateway-nginx/ 2>/dev/null")
        if exit_code == 0:
            # Check nginx config structure
            exit_code, out, _ = run_cmd(ssh, "cat /home/ubuntu/gateway-nginx/nginx.conf 2>/dev/null || cat /home/ubuntu/gateway-nginx/default.conf 2>/dev/null")
            print(f"  Gateway nginx config structure: {out[:1000]}")
            
            # Try to find where includes are
            exit_code, out, _ = run_cmd(ssh, "find /home/ubuntu/gateway-nginx/ -name '*.conf' 2>/dev/null | head -20")
            
            # Create conf.d if it doesn't exist and add include
            run_cmd(ssh, "mkdir -p /home/ubuntu/gateway-nginx/conf.d/")
            conf_path = f"/home/ubuntu/gateway-nginx/conf.d/{uid}.conf"
            run_cmd(ssh, f"cat > {conf_path} << 'CONFEOF'\n{conf_content}\nCONFEOF")
            
            # Check if the main config includes conf.d
            exit_code, out, _ = run_cmd(ssh, "grep -r 'include.*conf.d' /home/ubuntu/gateway-nginx/ 2>/dev/null || echo 'NO_INCLUDE'")
            if "NO_INCLUDE" in out:
                print("  Need to add include directive to nginx config")
                # Try to find the server block and add include
                exit_code, out, _ = run_cmd(ssh, "find /home/ubuntu/gateway-nginx/ -name '*.conf' -not -path '*/conf.d/*' | head -5")
                conf_files = [f.strip() for f in out.strip().split('\n') if f.strip()]
                if conf_files:
                    for cf in conf_files:
                        exit_code, out, _ = run_cmd(ssh, f"grep -c 'server' {cf} 2>/dev/null")
                        if out.strip() and int(out.strip()) > 0:
                            # Add include before the last closing brace of server block
                            run_cmd(ssh, f"grep -q 'include /home/ubuntu/gateway-nginx/conf.d' {cf} || sed -i '/server {{/,/}}/{{ /location/i\\    include /home/ubuntu/gateway-nginx/conf.d/*.conf;' {cf}")
                            break
            
            run_cmd(ssh, "docker exec gateway-nginx nginx -t 2>&1 && docker exec gateway-nginx nginx -s reload 2>&1")
        else:
            # Fall back to /etc/nginx
            run_cmd(ssh, f"sudo tee /etc/nginx/conf.d/{uid}.conf << 'CONFEOF'\n{conf_content}\nCONFEOF")
            run_cmd(ssh, "sudo nginx -t 2>&1 && sudo nginx -s reload 2>&1")


def ensure_network(ssh, uid, prefix):
    """Ensure project containers are connected to the gateway nginx network."""
    # Find gateway nginx container and its network
    exit_code, out, _ = run_cmd(ssh, "docker inspect gateway-nginx --format='{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null")
    if exit_code != 0:
        print("  gateway-nginx container not found, checking for other nginx containers...")
        exit_code, out, _ = run_cmd(ssh, "docker ps --format '{{.Names}}' | grep -i nginx")
        return
    
    gateway_networks = out.strip().split()
    if not gateway_networks:
        print("  Could not determine gateway network")
        return
    
    gateway_net = gateway_networks[0]
    print(f"  Gateway nginx is on network: {gateway_net}")
    
    # Connect project containers to gateway network
    containers = [f"{prefix}-h5", f"{prefix}-admin", f"{prefix}-backend"]
    for container in containers:
        exit_code, out, _ = run_cmd(ssh, f"docker network connect {gateway_net} {container} 2>&1 || echo 'ALREADY_CONNECTED'")


def verify_links(ssh):
    urls = {
        "H5 Frontend": f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/",
        "Admin Frontend": f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/",
        "API Docs": f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs",
    }
    
    results = {}
    for name, url in urls.items():
        exit_code, out, _ = run_cmd(ssh, f"curl -sL -o /dev/null -w '%{{http_code}}' --max-time 30 '{url}'")
        status = out.strip().replace("'", "")
        results[name] = status
        print(f"  {name}: {url} -> HTTP {status}")
    
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS:")
    print("=" * 60)
    all_ok = True
    for name, status in results.items():
        ok = status in ("200", "307", "302", "301")
        print(f"  {'OK' if ok else 'FAIL'} | {name}: HTTP {status}")
        if not ok:
            all_ok = False
    
    if not all_ok:
        print("\nSome links failed. Checking container logs...")
        run_cmd(ssh, f"cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml logs --tail=50 2>&1")
    
    return results


if __name__ == "__main__":
    main()
