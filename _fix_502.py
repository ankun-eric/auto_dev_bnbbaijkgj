import paramiko
import sys

def ssh_exec(host, cmd, timeout=30):
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

new_config = f'''
        # ===== BINI HEALTH: Miniprogram ZIP downloads =====
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
        # BINI HEALTH END
'''

print("Step 1: Backup current nginx.conf on front proxy...")
out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak.502fix")
print(f"Backup: {out}{err}")

print("\nStep 2: Get current config and locate old BINI HEALTH section...")
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

old_section = current_config[start_idx:end_idx]
print(f"Found old section at position {start_idx}-{end_idx}")
print(f"Old section length: {len(old_section)} chars")

new_section = new_config.strip()
updated_config = current_config[:start_idx] + new_section + current_config[end_idx:]

import tempfile, os
tmp_path = '/tmp/nginx_fix_502.conf'

sftp_ssh = paramiko.SSHClient()
sftp_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
sftp_ssh.connect(FRONT_HOST, username='ubuntu', password='Bangbang987', timeout=15)
sftp = sftp_ssh.open_sftp()
with sftp.file(tmp_path, 'w') as f:
    f.write(updated_config)
sftp.close()

print("\nStep 3: Copy new config into gateway-nginx container...")
out, err = ssh_exec(FRONT_HOST, f"docker cp {tmp_path} gateway-nginx:/etc/nginx/nginx.conf")
print(f"Copy: {out}{err}")

print("\nStep 4: Test nginx config...")
out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -t 2>&1")
print(f"Test: {out}{err}")

if "successful" in (out + err).lower():
    print("\nStep 5: Reload nginx...")
    out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -s reload 2>&1")
    print(f"Reload: {out}{err}")
    
    import time
    time.sleep(2)
    
    print("\nStep 6: Verify access...")
    out, err = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/ 2>/dev/null")
    print(f"H5 status: {out}")
    
    out, err = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/admin/ 2>/dev/null")
    print(f"Admin status: {out}")
    
    out, err = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/api/health 2>/dev/null")
    print(f"API health status: {out}")
else:
    print("ERROR: nginx config test failed, restoring backup...")
    out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx cp /etc/nginx/nginx.conf.bak.502fix /etc/nginx/nginx.conf")
    print(f"Restored: {out}{err}")

sftp_ssh.close()
print("\nDone!")
