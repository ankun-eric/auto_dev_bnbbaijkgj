import paramiko
import sys
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

FRONT_HOST = 'newbb.bangbangvip.com'
TEST_HOST = 'newbb.test.bangbangvip.com'
PROJECT_ID = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'

print("Step 1: Get current nginx.conf from front proxy...")
out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx cat /etc/nginx/nginx.conf")
current_config = out

start_marker = "# ===== BINI HEALTH: Miniprogram ZIP downloads ====="
end_marker = "# BINI HEALTH END"

start_idx = current_config.find(start_marker)
end_idx = current_config.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Could not find BINI HEALTH section markers")
    sys.exit(1)

end_idx = end_idx + len(end_marker)

new_section = f'''# ===== BINI HEALTH: Miniprogram ZIP downloads =====
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
        # BINI HEALTH END'''

updated_config = current_config[:start_idx] + new_section + current_config[end_idx:]

print("Step 2: Upload new config to server...")
sftp_ssh = paramiko.SSHClient()
sftp_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
sftp_ssh.connect(FRONT_HOST, username='ubuntu', password='Bangbang987', timeout=15)
sftp = sftp_ssh.open_sftp()
with sftp.file('/tmp/nginx_fix_502.conf', 'w') as f:
    f.write(updated_config)
sftp.close()
sftp_ssh.close()

print("Step 3: Copy into container using cat redirect...")
out, err = ssh_exec(FRONT_HOST, "docker exec -i gateway-nginx sh -c 'cat > /tmp/nginx_new.conf' < /tmp/nginx_fix_502.conf && docker exec gateway-nginx cp /tmp/nginx_new.conf /etc/nginx/nginx.conf")
print(f"Copy result: stdout={out}, stderr={err}")

print("\nStep 4: Verify the config was updated...")
out, err = ssh_exec(FRONT_HOST, f"docker exec gateway-nginx grep -c 'proxy_ssl_server_name' /etc/nginx/nginx.conf")
print(f"proxy_ssl_server_name count: {out.strip()}")

print("\nStep 5: Test nginx config...")
out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -t 2>&1")
combined = out + err
print(f"Test result: {combined}")

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
        out, err = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com{path} 2>/dev/null")
        print(f"  {name}: {out.strip()}")
else:
    print("ERROR: nginx config test failed!")
    out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx cat /etc/nginx/nginx.conf | grep -A2 -B2 'proxy_ssl'")
    print(f"Debug: {out}")

print("\nDone!")
