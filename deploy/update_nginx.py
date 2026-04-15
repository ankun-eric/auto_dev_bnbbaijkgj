import paramiko

SERVER = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_PATH = f'/autodev/{DEPLOY_ID}'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=USER, password=PASSWORD)

nginx_conf = f"""# ===== Project: {DEPLOY_ID} =====

# Backend API docs (FastAPI serves at /docs, /openapi.json)
location = {BASE_PATH}/api/docs {{
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $target_backend {DEPLOY_ID}-backend;
    rewrite ^{BASE_PATH}/api/docs$ /docs break;
    proxy_pass http://$target_backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}}

location = {BASE_PATH}/api/openapi.json {{
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $target_backend {DEPLOY_ID}-backend;
    rewrite ^{BASE_PATH}/api/openapi.json$ /openapi.json break;
    proxy_pass http://$target_backend:8000;
    proxy_set_header Host $host;
}}

location = {BASE_PATH}/api/redoc {{
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $target_backend {DEPLOY_ID}-backend;
    rewrite ^{BASE_PATH}/api/redoc$ /redoc break;
    proxy_pass http://$target_backend:8000;
    proxy_set_header Host $host;
}}

# Backend API
location {BASE_PATH}/api/ {{
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $target_backend {DEPLOY_ID}-backend;
    rewrite ^{BASE_PATH}/api/(.*) /api/$1 break;
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

# File uploads/downloads
location {BASE_PATH}/uploads/ {{
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $target_backend {DEPLOY_ID}-backend;
    rewrite ^{BASE_PATH}/uploads/(.*) /uploads/$1 break;
    proxy_pass http://$target_backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}}

# Admin web (Next.js SSR - do NOT strip prefix)
location {BASE_PATH}/admin/ {{
    resolver 127.0.0.11 valid=10s ipv6=off;
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

# Admin _next static assets
location {BASE_PATH}/admin/_next/ {{
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $target_admin {DEPLOY_ID}-admin;
    proxy_pass http://$target_admin:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
}}

# H5 Frontend (Next.js SSR - do NOT strip prefix)
location {BASE_PATH}/ {{
    resolver 127.0.0.11 valid=10s ipv6=off;
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

# H5 _next static assets
location {BASE_PATH}/_next/ {{
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $target_h5 {DEPLOY_ID}-h5;
    proxy_pass http://$target_h5:3001;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
}}

# miniprogram zip
location ~ ^{BASE_PATH}/(miniprogram_.+\\.zip)$ {{
    alias /data/static/$1;
    default_type application/zip;
    add_header Content-Disposition "attachment";
    expires 30d;
}}
"""

conf_file = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf'
cmd = f"cat > {conf_file} << 'NGINX_CONF_EOF'\n{nginx_conf}\nNGINX_CONF_EOF"
stdin, stdout, stderr = ssh.exec_command(cmd)
stdout.channel.recv_exit_status()

stdin, stdout, stderr = ssh.exec_command('docker exec gateway nginx -t 2>&1')
out = stdout.read().decode()
code = stdout.channel.recv_exit_status()
print(f"nginx -t: {out.strip()} (exit {code})")

if code == 0:
    stdin, stdout, stderr = ssh.exec_command('docker exec gateway nginx -s reload 2>&1')
    stdout.channel.recv_exit_status()
    print("nginx reloaded!")
else:
    print("ERROR: nginx config invalid, not reloading")

ssh.close()
