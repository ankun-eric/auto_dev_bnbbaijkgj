import sys

DEPLOY_ID = sys.argv[1] if len(sys.argv) > 1 else "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = sys.argv[2] if len(sys.argv) > 2 else "noob-ai.test.bangbangvip.com"
NGINX_CONF = "/home/ubuntu/gateway/nginx.conf"

with open(NGINX_CONF, 'r') as f:
    content = f.read()

# Check if already present
if f"server_name {DEPLOY_ID}.{WILDCARD_BASE}" in content:
    print("Server block already exists, skipping.")
    sys.exit(0)

server_block = f"""
    # ===== Project: {DEPLOY_ID} (auto-generated) =====
    server {{
        listen 80;
        server_name {DEPLOY_ID}.{WILDCARD_BASE};
        return 301 https://$host$request_uri;
    }}

    server {{
        listen 443 ssl http2;
        server_name {DEPLOY_ID}.{WILDCARD_BASE};
        resolver 127.0.0.11 valid=10s ipv6=off;

        ssl_certificate     /etc/nginx/ssl/wildcard.{WILDCARD_BASE}.crt;
        ssl_certificate_key /etc/nginx/ssl/wildcard.{WILDCARD_BASE}.key;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        include /etc/nginx/conf.d/{DEPLOY_ID}.conf;
    }}
"""

last_brace = content.rfind('}')
if last_brace > 0:
    content = content[:last_brace] + server_block + '\n' + content[last_brace:]

with open(NGINX_CONF, 'w') as f:
    f.write(content)

print("Server block inserted successfully into nginx.conf")
