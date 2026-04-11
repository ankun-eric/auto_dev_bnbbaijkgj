#!/usr/bin/env python3
"""Update gateway routing and verify deployment."""

import sys
import time
import paramiko

HOST = "newbb.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
GATEWAY_DIR = "/home/ubuntu/gateway"
CONF_FILE = f"{GATEWAY_DIR}/conf.d/{DEPLOY_ID}.conf"


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return client


def run_ssh(client, cmd, timeout=60):
    print(f"  $ {cmd[:120]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  OUT: {out.strip()[:800]}")
    if err.strip():
        print(f"  ERR: {err.strip()[:400]}")
    return exit_code, out, err


def main():
    print("=" * 60)
    print("GATEWAY UPDATE & VERIFICATION")
    print("=" * 60)

    client = get_ssh_client()
    print("Connected!")

    # Step 1: Find gateway container
    print("\n[1] Finding gateway container...")
    rc, out, _ = run_ssh(client, "docker ps --format '{{.Names}}' | grep -i gateway")
    gateway_container = out.strip().split("\n")[0].strip() if out.strip() else ""
    if not gateway_container:
        rc, out, _ = run_ssh(client, "docker ps --format '{{.Names}}' | grep -i nginx")
        gateway_container = out.strip().split("\n")[0].strip() if out.strip() else ""
    print(f"  Gateway container: {gateway_container}")

    # Step 2: Check if conf.d exists
    print("\n[2] Checking gateway conf.d support...")
    rc, out, _ = run_ssh(client, f"cat {GATEWAY_DIR}/nginx.conf | grep 'conf.d'")
    has_confd = "conf.d" in out

    # Step 3: Backup nginx.conf
    print("\n[3] Backing up nginx.conf...")
    backup_cmd = f"cp {GATEWAY_DIR}/nginx.conf {GATEWAY_DIR}/nginx.conf.bak.$(date +%Y%m%d%H%M%S)"
    run_ssh(client, backup_cmd)

    # Step 4: Extract SSL snapshot
    print("\n[4] Extracting SSL snapshot...")
    if gateway_container:
        run_ssh(client, f"docker exec {gateway_container} nginx -T 2>/dev/null | grep -E 'listen.*443.*ssl|ssl_certificate|ssl_certificate_key|ssl_protocols|ssl_ciphers' > /tmp/ssl_snapshot_before.txt")
        rc, ssl_snap, _ = run_ssh(client, "cat /tmp/ssl_snapshot_before.txt")
        print(f"  SSL snapshot: {ssl_snap.strip()[:300]}")

    # Step 5: Write routes conf
    print("\n[5] Writing gateway routes config...")
    routes_conf = f"""# ===== Project: {DEPLOY_ID} =====

location /autodev/{DEPLOY_ID}/api/ {{
    set $target_backend {DEPLOY_ID}-backend;
    rewrite ^/autodev/{DEPLOY_ID}/api/(.*) /api/$1 break;
    proxy_pass http://$target_backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}}

location /autodev/{DEPLOY_ID}/uploads/ {{
    set $target_backend {DEPLOY_ID}-backend;
    rewrite ^/autodev/{DEPLOY_ID}/uploads/(.*) /uploads/$1 break;
    proxy_pass http://$target_backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}}

location /autodev/{DEPLOY_ID}/admin/ {{
    set $target_admin {DEPLOY_ID}-admin;
    proxy_pass http://$target_admin:3000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
}}

location /autodev/{DEPLOY_ID}/admin/_next/ {{
    set $target_admin {DEPLOY_ID}-admin;
    proxy_pass http://$target_admin:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
}}

location /autodev/{DEPLOY_ID}/ {{
    set $target_h5 {DEPLOY_ID}-h5;
    proxy_pass http://$target_h5:3001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
}}

location /autodev/{DEPLOY_ID}/_next/ {{
    set $target_h5 {DEPLOY_ID}-h5;
    proxy_pass http://$target_h5:3001;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
}}
"""

    if has_confd:
        print("  Using conf.d/ directory approach...")
        run_ssh(client, f"mkdir -p {GATEWAY_DIR}/conf.d")
        # Write conf file via heredoc
        escaped = routes_conf.replace("'", "'\"'\"'")
        write_cmd = f"cat > {CONF_FILE} << 'NGINX_CONF_EOF'\n{routes_conf}\nNGINX_CONF_EOF"
        run_ssh(client, write_cmd)
    else:
        print("  conf.d not found, checking if already has project routes...")
        rc, out, _ = run_ssh(client, f"grep -c '{DEPLOY_ID}' {GATEWAY_DIR}/nginx.conf")
        if int(out.strip() or "0") > 0:
            print("  Routes already exist in nginx.conf")
        else:
            print("  Adding conf.d include to nginx.conf...")
            run_ssh(client, f"mkdir -p {GATEWAY_DIR}/conf.d")
            # Add include directive before closing brace of server block
            run_ssh(client, f"sed -i '/^}}/i\\    include /etc/nginx/conf.d/*.conf;' {GATEWAY_DIR}/nginx.conf")
            write_cmd = f"cat > {CONF_FILE} << 'NGINX_CONF_EOF'\n{routes_conf}\nNGINX_CONF_EOF"
            run_ssh(client, write_cmd)

    # Step 6: Connect gateway to project network
    print("\n[6] Connecting gateway to project network...")
    network_name = f"{DEPLOY_ID}-network"
    if gateway_container:
        rc, out, err = run_ssh(client, f"docker network connect {network_name} {gateway_container} 2>&1")
        if "already exists" in out or "already exists" in err:
            print("  Already connected")
        else:
            print(f"  Connected to {network_name}")

    # Step 7: Test nginx config
    print("\n[7] Testing nginx configuration...")
    if gateway_container:
        rc, out, err = run_ssh(client, f"docker exec {gateway_container} nginx -t 2>&1")
        if rc != 0:
            print(f"  NGINX CONFIG ERROR! Rolling back...")
            run_ssh(client, f"ls -t {GATEWAY_DIR}/nginx.conf.bak.* | head -1 | xargs -I{{}} cp {{}} {GATEWAY_DIR}/nginx.conf")
            if has_confd:
                run_ssh(client, f"rm -f {CONF_FILE}")
            sys.exit(1)
        print("  Nginx config OK!")

    # Step 8: Reload nginx
    print("\n[8] Reloading nginx...")
    if gateway_container:
        rc, out, err = run_ssh(client, f"docker exec {gateway_container} nginx -s reload 2>&1")
        print(f"  Reload result: {out.strip() or 'OK'}")
    
    time.sleep(2)

    # Step 9: Verify SSL still works
    print("\n[9] Verifying SSL certificate...")
    rc, out, err = run_ssh(client, f"curl -vI https://{HOST}/ 2>&1 | grep -iE 'SSL certificate|subject|issuer|expire|SSL connection|HTTP/'")
    print(f"  SSL check: {out.strip()[:300]}")

    # Step 10: Health checks
    print("\n[10] Health checks...")
    
    urls = [
        (f"https://{HOST}/autodev/{DEPLOY_ID}/api/health", "Backend API health"),
        (f"https://{HOST}/autodev/{DEPLOY_ID}/", "H5 Frontend"),
        (f"https://{HOST}/autodev/{DEPLOY_ID}/docs", "API Docs"),
    ]
    
    results = {}
    for url, name in urls:
        rc, out, err = run_ssh(client, f"curl -s -o /dev/null -w '%{{http_code}}' '{url}'")
        status = out.strip()
        print(f"  {name}: HTTP {status}")
        results[name] = status

    print("\n" + "=" * 60)
    print("GATEWAY UPDATE COMPLETE!")
    print("=" * 60)
    for name, status in results.items():
        print(f"  {name}: {status}")
    
    client.close()
    return results


if __name__ == "__main__":
    main()
