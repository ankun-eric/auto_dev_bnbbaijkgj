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

def sftp_write(host, path, content):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username='ubuntu', password='Bangbang987', timeout=15)
    sftp = ssh.open_sftp()
    with sftp.file(path, 'w') as f:
        f.write(content)
    sftp.close()
    ssh.close()

FRONT_HOST = 'newbb.bangbangvip.com'
TEST_HOST = 'newbb.test.bangbangvip.com'
PROJECT_ID = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'

print("Step 1: Read current nginx.conf from host path...")
out, err = ssh_exec(FRONT_HOST, "cat /home/ubuntu/gateway/nginx.conf")
current_config = out
print(f"Current config length: {len(current_config)} chars")

start_marker = "# ===== BINI HEALTH: Miniprogram ZIP downloads ====="
end_marker = "# BINI HEALTH END"

start_idx = current_config.find(start_marker)
end_idx = current_config.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Could not find BINI HEALTH section markers")
    exit(1)

end_idx = end_idx + len(end_marker)
print(f"Found BINI HEALTH section at {start_idx}-{end_idx}")

new_section = f"""# ===== BINI HEALTH: Miniprogram ZIP downloads =====
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

updated_config = current_config[:start_idx] + new_section + current_config[end_idx:]

print("\nStep 2: Backup original config...")
out, err = ssh_exec(FRONT_HOST, "cp /home/ubuntu/gateway/nginx.conf /home/ubuntu/gateway/nginx.conf.bak.502fix")
print(f"Backup done")

print("\nStep 3: Write updated config to host path...")
sftp_write(FRONT_HOST, '/home/ubuntu/gateway/nginx.conf', updated_config)
print("Written!")

print("\nStep 4: Verify content was updated...")
out, err = ssh_exec(FRONT_HOST, "grep -c 'proxy_ssl_server_name' /home/ubuntu/gateway/nginx.conf")
print(f"proxy_ssl_server_name count: {out.strip()}")

print("\nStep 5: Test nginx config...")
out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -t 2>&1")
combined = out + err
print(f"Test: {combined.strip()}")

if "successful" in combined.lower():
    print("\nStep 6: Reload nginx...")
    out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -s reload 2>&1")
    print(f"Reload: {out}{err}")
    
    time.sleep(3)
    
    print("\nStep 7: Verify access...")
    for path, name in [
        (f"/autodev/{PROJECT_ID}/", "H5"),
        (f"/autodev/{PROJECT_ID}/admin/", "Admin"),
        (f"/autodev/{PROJECT_ID}/api/health", "API Health"),
    ]:
        out, err = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com{path}")
        print(f"  {name}: {out.strip()}")
else:
    print("\nERROR: nginx config test failed! Restoring backup...")
    out, err = ssh_exec(FRONT_HOST, "cp /home/ubuntu/gateway/nginx.conf.bak.502fix /home/ubuntu/gateway/nginx.conf")
    out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -s reload 2>&1")
    print("Backup restored and nginx reloaded")

print("\nDone!")
