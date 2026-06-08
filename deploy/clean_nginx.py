"""Clean nginx.conf - remove auto-generated server block for our project."""
NGINX_CONF = "/home/ubuntu/gateway/nginx.conf"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

with open(NGINX_CONF, 'r') as f:
    lines = f.readlines()

new_lines = []
skip = 0
for line in lines:
    if f'Project: {DEPLOY_ID} (auto-generated)' in line:
        skip = 2
        continue
    if skip > 0:
        if line.strip() == '}':
            skip -= 1
        continue
    new_lines.append(line)

with open(NGINX_CONF, 'w') as f:
    f.writelines(new_lines)

print(f"CLEANED: removed auto-generated block for {DEPLOY_ID}")
print(f"Lines: {len(lines)} -> {len(new_lines)}")
