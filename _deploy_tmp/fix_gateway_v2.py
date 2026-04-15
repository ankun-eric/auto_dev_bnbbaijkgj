import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USERNAME = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def ssh_exec(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USERNAME, password=PASSWORD, timeout=30)
    print("Connected")

    static_dir = f"/home/ubuntu/{DEPLOY_ID}/static"

    print("=== Step 1: Read gateway docker-compose.yml ===")
    out_dc, _ = ssh_exec(client, "cat /home/ubuntu/gateway/docker-compose.yml")
    print(out_dc)

    print("\n=== Step 2: Add static volume mount to gateway ===")
    volume_line = f"      - {static_dir}:/data/static:ro"
    if static_dir not in out_dc:
        lines = out_dc.split('\n')
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if '- /home/ubuntu/gateway/conf.d' in line or '- /home/ubuntu/gateway/ssl' in line:
                if volume_line not in '\n'.join(new_lines):
                    new_lines.append(volume_line)
        updated_dc = '\n'.join(new_lines)

        ssh_exec(client, f"""cat > /home/ubuntu/gateway/docker-compose.yml << 'DCEOF'
{updated_dc}
DCEOF""")
        print("Added static volume mount")
        out_dc2, _ = ssh_exec(client, "cat /home/ubuntu/gateway/docker-compose.yml")
        print(out_dc2)
    else:
        print("Volume already mounted")

    print("\n=== Step 3: Add static location to project nginx conf ===")
    conf_file = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
    out_check, _ = ssh_exec(client, f"grep -c 'static' {conf_file} 2>/dev/null || echo 0")
    
    static_block = f"""
# Miniprogram zip static files
location /autodev/{DEPLOY_ID}/static/ {{
    alias /data/static/;
    autoindex off;
    expires 30d;
    add_header Cache-Control "public, immutable";
}}"""

    if out_check.strip() == "0":
        ssh_exec(client, f"""cat >> {conf_file} << 'CONFEOF'
{static_block}
CONFEOF""")
        print("Added static location block")
    else:
        print("Static location already exists")

    out_conf, _ = ssh_exec(client, f"cat {conf_file}")
    print(f"Updated conf (last 500 chars):\n...{out_conf[-500:]}")

    print("\n=== Step 4: Restart gateway container ===")
    out, err = ssh_exec(client, "cd /home/ubuntu/gateway && docker compose down 2>&1")
    print(f"Down: {out} {err}")
    time.sleep(2)
    out, err = ssh_exec(client, "cd /home/ubuntu/gateway && docker compose up -d 2>&1")
    print(f"Up: {out} {err}")
    time.sleep(5)

    print("\n=== Step 5: Verify nginx config ===")
    out, err = ssh_exec(client, "docker exec gateway nginx -t 2>&1")
    print(f"nginx -t: {out} {err}")

    print("\n=== Step 6: Check static files inside container ===")
    out, _ = ssh_exec(client, "docker exec gateway ls -la /data/static/ 2>&1")
    print(f"Container static dir: {out}")

    print("\n=== Step 7: Verify URLs ===")
    time.sleep(2)
    out_files, _ = ssh_exec(client, f"ls {static_dir}/")
    for f in out_files.split('\n'):
        f = f.strip()
        if f.endswith('.zip'):
            url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/static/{f}"
            out, _ = ssh_exec(client, f"curl -s -o /dev/null -w '%{{http_code}}' '{url}' --max-time 10")
            print(f"  {f}: HTTP {out}")

    client.close()


if __name__ == '__main__':
    main()
