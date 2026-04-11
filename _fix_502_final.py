import paramiko
import time

def ssh_exec(host, cmd, timeout=60):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username='ubuntu', password='Bangbang987', timeout=15)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out, err

def sftp_write_inplace(host, path, content):
    """Write to file in-place to preserve inode for Docker bind mounts"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username='ubuntu', password='Bangbang987', timeout=15)
    sftp = ssh.open_sftp()
    with sftp.file('/tmp/nginx_fix_tmp.conf', 'w') as f:
        f.write(content)
    sftp.close()
    stdin, stdout, stderr = ssh.exec_command(f'cat /tmp/nginx_fix_tmp.conf > {path}', timeout=30)
    stdout.read()
    stderr.read()
    ssh.close()

FRONT_HOST = 'newbb.bangbangvip.com'
TEST_HOST = 'newbb.test.bangbangvip.com'
PROJECT_ID = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'

print("Step 1: Read original backup config...")
out, err = ssh_exec(FRONT_HOST, "cat /home/ubuntu/gateway/nginx.conf.bak.502fix")
config = out
print(f"Config length: {len(config)} chars")

# Fix 1: The 29c7b754 uploads location is missing its closing brace
broken_section = """        location /autodev/29c7b754-064a-43bc-8eed-a89515607c5d/uploads/ {
            set $target_backend 29c7b754-064a-43bc-8eed-a89515607c5d-backend;
            rewrite ^/autodev/29c7b754-064a-43bc-8eed-a89515607c5d/uploads/(.*) /uploads/$1 break;
            proxy_pass http://$target_backend:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;

        # ===== Project: da347c81"""

fixed_section = """        location /autodev/29c7b754-064a-43bc-8eed-a89515607c5d/uploads/ {
            set $target_backend 29c7b754-064a-43bc-8eed-a89515607c5d-backend;
            rewrite ^/autodev/29c7b754-064a-43bc-8eed-a89515607c5d/uploads/(.*) /uploads/$1 break;
            proxy_pass http://$target_backend:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ===== Project: da347c81"""

if broken_section in config:
    config = config.replace(broken_section, fixed_section)
    print("Fix 1: Fixed missing closing brace for 29c7b754 uploads location")
else:
    print("Fix 1: Could not find broken section - trying alternate match")
    alt_broken = """            proxy_set_header X-Real-IP $remote_addr;

        # ===== Project: da347c81-7ce1-4d83-bca2-aa863849b5e1 =====

        location /autodev/da347c81"""
    alt_fixed = """            proxy_set_header X-Real-IP $remote_addr;
        }

        # ===== Project: da347c81-7ce1-4d83-bca2-aa863849b5e1 =====

        location /autodev/da347c81"""
    if alt_broken in config:
        config = config.replace(alt_broken, alt_fixed)
        print("Fix 1: Fixed using alternate match")
    else:
        print("Fix 1: WARNING - Could not find broken section at all")

# Fix 2: Update BINI HEALTH section
start_marker = "# ===== BINI HEALTH: Miniprogram ZIP downloads ====="
end_marker = "# BINI HEALTH END"

start_idx = config.find(start_marker)
end_idx = config.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Could not find BINI HEALTH section")
    exit(1)

end_idx = end_idx + len(end_marker)

new_bini_section = f"""# ===== BINI HEALTH: Miniprogram ZIP downloads =====
        location ~ ^/autodev/{PROJECT_ID}/miniprogram_.*\\.zip$ {{
            root /usr/share/nginx/html;
            default_type application/octet-stream;
            add_header Content-Disposition attachment;
        }}

        location ~ ^/autodev/{PROJECT_ID}/verify_miniprogram_.*\\.zip$ {{
            root /usr/share/nginx/html;
            default_type application/octet-stream;
            add_header Content-Disposition attachment;
        }}

        # ===== BINI HEALTH: AI Health Manager =====

        location ~ ^/autodev/{PROJECT_ID}/apk/.*\\.apk$ {{
            root /usr/share/nginx/html;
            default_type application/vnd.android.package-archive;
            add_header Content-Disposition attachment;
        }}

        # APK downloads (root level)
        location ~ ^/autodev/{PROJECT_ID}/.*\\.apk$ {{
            proxy_pass https://{TEST_HOST};
            proxy_ssl_server_name on;
            proxy_ssl_name {TEST_HOST};
            proxy_set_header Host {TEST_HOST};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}

        location /autodev/{PROJECT_ID}/api/ {{
            proxy_pass https://{TEST_HOST}/autodev/{PROJECT_ID}/api/;
            proxy_ssl_server_name on;
            proxy_ssl_name {TEST_HOST};
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host {TEST_HOST};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }}

        # File uploads
        location /autodev/{PROJECT_ID}/uploads/ {{
            proxy_pass https://{TEST_HOST}/autodev/{PROJECT_ID}/uploads/;
            proxy_ssl_server_name on;
            proxy_ssl_name {TEST_HOST};
            proxy_http_version 1.1;
            proxy_set_header Host {TEST_HOST};
        }}

        # Admin Dashboard
        location /autodev/{PROJECT_ID}/admin/ {{
            proxy_pass https://{TEST_HOST}/autodev/{PROJECT_ID}/admin/;
            proxy_ssl_server_name on;
            proxy_ssl_name {TEST_HOST};
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host {TEST_HOST};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }}

        # Admin _next static assets
        location /autodev/{PROJECT_ID}/admin/_next/ {{
            proxy_pass https://{TEST_HOST}/autodev/{PROJECT_ID}/admin/_next/;
            proxy_ssl_server_name on;
            proxy_ssl_name {TEST_HOST};
            proxy_http_version 1.1;
            proxy_set_header Host {TEST_HOST};
            proxy_cache_bypass $http_upgrade;
        }}

        # H5 _next static assets
        location /autodev/{PROJECT_ID}/_next/ {{
            proxy_pass https://{TEST_HOST}/autodev/{PROJECT_ID}/_next/;
            proxy_ssl_server_name on;
            proxy_ssl_name {TEST_HOST};
            proxy_http_version 1.1;
            proxy_set_header Host {TEST_HOST};
            proxy_cache_bypass $http_upgrade;
        }}

        # H5 User Frontend (catch-all for this project)
        location /autodev/{PROJECT_ID}/ {{
            proxy_pass https://{TEST_HOST}/autodev/{PROJECT_ID}/;
            proxy_ssl_server_name on;
            proxy_ssl_name {TEST_HOST};
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host {TEST_HOST};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }}
        # BINI HEALTH END"""

config = config[:start_idx] + new_bini_section + config[end_idx:]
print(f"Fix 2: Updated BINI HEALTH section to proxy via {TEST_HOST}")

print(f"\nUpdated config length: {len(config)} chars")

print("\nStep 2: Write config in-place (preserving inode)...")
sftp_write_inplace(FRONT_HOST, '/home/ubuntu/gateway/nginx.conf', config)
print("Written!")

print("\nStep 3: Restart gateway-nginx...")
out, err = ssh_exec(FRONT_HOST, "docker restart gateway-nginx 2>&1")
print(f"Restart: {out.strip()}")

time.sleep(5)

print("\nStep 4: Check gateway status...")
out, err = ssh_exec(FRONT_HOST, "docker ps --filter name=gateway-nginx --format '{{.Names}}|{{.Status}}'")
print(f"Status: {out.strip()}")

if "Up" in out and "Restarting" not in out:
    print("\nStep 5: Verify access...")
    for path, name in [
        (f"/autodev/{PROJECT_ID}/", "H5"),
        (f"/autodev/{PROJECT_ID}/admin/", "Admin"),
        (f"/autodev/{PROJECT_ID}/api/health", "API Health"),
    ]:
        out, err = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com{path}")
        print(f"  {name}: {out.strip()}")
else:
    print("\nGateway still not up. Checking logs...")
    out, err = ssh_exec(FRONT_HOST, "docker logs gateway-nginx --tail 5 2>&1")
    print(f"Logs: {out}{err}")

print("\nDone!")
