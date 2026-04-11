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

FRONT_HOST = 'newbb.bangbangvip.com'
TEST_HOST = 'newbb.test.bangbangvip.com' 
PROJECT_ID = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'
CONF = '/home/ubuntu/gateway/nginx.conf'

print("Step 1: Check current inode...")
out, _ = ssh_exec(FRONT_HOST, f"ls -i {CONF}")
print(f"Current inode: {out.strip()}")

print("\nStep 2: Fix missing closing brace for 29c7b754 uploads using sed...")
# The issue: after X-Real-IP line, there's no closing } before the da347c81 comment
# Using sed to insert a closing } after the X-Real-IP line within 29c7b754 uploads block
cmd = r"""python3 -c "
import re

with open('/home/ubuntu/gateway/nginx.conf', 'r') as f:
    content = f.read()

# Fix 1: Missing closing brace
old = '            proxy_set_header X-Real-IP \$remote_addr;\n\n        # ===== Project: da347c81'
new = '            proxy_set_header X-Real-IP \$remote_addr;\n        }\n\n        # ===== Project: da347c81'
content = content.replace(old, new)

# Fix 2: Replace BINI HEALTH direct IP proxy with HTTPS proxy through test server
import re

# Find BINI HEALTH section
start = content.find('# ===== BINI HEALTH: Miniprogram ZIP downloads =====')
end = content.find('# BINI HEALTH END')
if start >= 0 and end >= 0:
    end += len('# BINI HEALTH END')
    old_section = content[start:end]
    
    new_section = '''# ===== BINI HEALTH: Miniprogram ZIP downloads =====
        location ~ ^/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_.*\\\\.zip\$ {
            root /usr/share/nginx/html;
            default_type application/octet-stream;
            add_header Content-Disposition attachment;
        }

        location ~ ^/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/verify_miniprogram_.*\\\\.zip\$ {
            root /usr/share/nginx/html;
            default_type application/octet-stream;
            add_header Content-Disposition attachment;
        }

        # ===== BINI HEALTH: AI Health Manager =====

        location ~ ^/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/apk/.*\\\\.apk\$ {
            root /usr/share/nginx/html;
            default_type application/vnd.android.package-archive;
            add_header Content-Disposition attachment;
        }

        location ~ ^/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/.*\\\\.apk\$ {
            proxy_pass https://newbb.test.bangbangvip.com;
            proxy_ssl_server_name on;
            proxy_ssl_name newbb.test.bangbangvip.com;
            proxy_set_header Host newbb.test.bangbangvip.com;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }

        location /autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api/ {
            proxy_pass https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api/;
            proxy_ssl_server_name on;
            proxy_ssl_name newbb.test.bangbangvip.com;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \\'upgrade\\';
            proxy_set_header Host newbb.test.bangbangvip.com;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_cache_bypass \$http_upgrade;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }

        location /autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/ {
            proxy_pass https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/;
            proxy_ssl_server_name on;
            proxy_ssl_name newbb.test.bangbangvip.com;
            proxy_http_version 1.1;
            proxy_set_header Host newbb.test.bangbangvip.com;
        }

        location /autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/ {
            proxy_pass https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/;
            proxy_ssl_server_name on;
            proxy_ssl_name newbb.test.bangbangvip.com;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \\'upgrade\\';
            proxy_set_header Host newbb.test.bangbangvip.com;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_cache_bypass \$http_upgrade;
        }

        location /autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/_next/ {
            proxy_pass https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/_next/;
            proxy_ssl_server_name on;
            proxy_ssl_name newbb.test.bangbangvip.com;
            proxy_http_version 1.1;
            proxy_set_header Host newbb.test.bangbangvip.com;
            proxy_cache_bypass \$http_upgrade;
        }

        location /autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/_next/ {
            proxy_pass https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/_next/;
            proxy_ssl_server_name on;
            proxy_ssl_name newbb.test.bangbangvip.com;
            proxy_http_version 1.1;
            proxy_set_header Host newbb.test.bangbangvip.com;
            proxy_cache_bypass \$http_upgrade;
        }

        location /autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/ {
            proxy_pass https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/;
            proxy_ssl_server_name on;
            proxy_ssl_name newbb.test.bangbangvip.com;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \\'upgrade\\';
            proxy_set_header Host newbb.test.bangbangvip.com;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_cache_bypass \$http_upgrade;
        }
        # BINI HEALTH END'''
    
    content = content[:start] + new_section + content[end:]

# Write in-place using truncate+write to preserve inode
with open('/home/ubuntu/gateway/nginx.conf', 'r+') as f:
    f.seek(0)
    f.write(content)
    f.truncate()

print('Done')
"
"""
out, err = ssh_exec(FRONT_HOST, cmd, timeout=30)
print(f"Python fix output: {out.strip()}")
if err:
    print(f"STDERR: {err.strip()}")

print("\nStep 3: Check inode preserved...")
out, _ = ssh_exec(FRONT_HOST, f"ls -i {CONF}")
print(f"Current inode: {out.strip()}")

print("\nStep 4: Verify fix 1...")
out, _ = ssh_exec(FRONT_HOST, "grep -c 'proxy_ssl_server_name' /home/ubuntu/gateway/nginx.conf")
print(f"proxy_ssl_server_name count: {out.strip()}")

print("\nStep 5: Test config via docker...")
out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -t 2>&1")
print(f"Test: {(out+err).strip()}")

if "successful" in (out+err).lower():
    print("\nStep 6: Reload nginx...")
    out, err = ssh_exec(FRONT_HOST, "docker exec gateway-nginx nginx -s reload 2>&1")
    print(f"Reload: {(out+err).strip()}")
elif "Restarting" in ssh_exec(FRONT_HOST, "docker ps --filter name=gateway --format '{{.Status}}'")[0]:
    print("\nContainer is restarting. Let me restart it after fix...")
    out, err = ssh_exec(FRONT_HOST, "docker restart gateway-nginx 2>&1")
    print(f"Restart: {out.strip()}")
    time.sleep(5)

time.sleep(3)

print("\nStep 7: Check status...")
out, _ = ssh_exec(FRONT_HOST, "docker ps --filter name=gateway-nginx --format '{{.Names}}|{{.Status}}'")
print(f"Status: {out.strip()}")

if "Up" in out and "Restarting" not in out:
    print("\nStep 8: Verify access...")
    for path, name in [
        (f"/autodev/{PROJECT_ID}/", "H5"),
        (f"/autodev/{PROJECT_ID}/admin/", "Admin"),
        (f"/autodev/{PROJECT_ID}/api/health", "API Health"),
    ]:
        out, _ = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com{path}")
        print(f"  {name}: {out.strip()}")
else:
    print("\nERROR: Gateway still not up!")
    out, err = ssh_exec(FRONT_HOST, "docker logs gateway-nginx --tail 5 2>&1")
    print(f"Logs:\n{out}{err}")

print("\nDone!")
