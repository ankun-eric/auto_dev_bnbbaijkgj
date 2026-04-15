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

    print("\n--- Checking gateway conf.d ---")
    out, _ = ssh_exec(client, f"cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf")
    print(f"Project conf:\n{out[:3000]}")

    print("\n--- Checking static dir ---")
    out, _ = ssh_exec(client, f"ls -la /home/ubuntu/{DEPLOY_ID}/static/")
    print(out)

    print("\n--- Gateway container mounts ---")
    out, _ = ssh_exec(client, "docker inspect gateway --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Mode}})\n{{end}}'")
    print(out)

    print("\n--- Checking nginx.conf ---")
    out, _ = ssh_exec(client, "cat /home/ubuntu/gateway/nginx.conf")
    print(out[:2000])

    print("\n--- Need to add static location to project conf ---")
    out, _ = ssh_exec(client, f"grep -c 'static' /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>/dev/null || echo 0")
    print(f"Static count in conf: {out}")

    static_block = f"""
# Miniprogram zip static files
location /autodev/{DEPLOY_ID}/static/ {{
    alias /data/static/;
    autoindex off;
    expires 30d;
    add_header Cache-Control "public, immutable";
}}
"""

    if out.strip() == "0" or out.strip() == "":
        print("\n--- Adding static file volume mount ---")
        
        out_dc, _ = ssh_exec(client, "cat /home/ubuntu/gateway/docker-compose.yml")
        print(f"Gateway docker-compose:\n{out_dc}")

        print("\n--- Checking if we can add volume mount ---")
        if f"{DEPLOY_ID}/static" not in out_dc:
            new_volume = f"      - /home/ubuntu/{DEPLOY_ID}/static:/data/{DEPLOY_ID}/static:ro"
            
            updated_dc = out_dc
            if 'volumes:' in updated_dc:
                lines = updated_dc.split('\n')
                new_lines = []
                added = False
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if not added and 'volumes:' in line and '- /' in (lines[i+1] if i+1 < len(lines) else ''):
                        new_lines.append(new_volume)
                        added = True
                if not added:
                    for i, line in enumerate(new_lines):
                        if line.strip().startswith('- /home/ubuntu/gateway/conf.d'):
                            new_lines.insert(i+1, new_volume)
                            added = True
                            break
                updated_dc = '\n'.join(new_lines)

            ssh_exec(client, f"""cat > /home/ubuntu/gateway/docker-compose.yml << 'DCEOF'
{updated_dc}
DCEOF""")
            print("Updated gateway docker-compose.yml with static volume")

        print("\n--- Adding static location to nginx conf ---")
        static_block_alias = f"""
# Miniprogram zip static files
location /autodev/{DEPLOY_ID}/static/ {{
    alias /data/{DEPLOY_ID}/static/;
    autoindex off;
    expires 30d;
    add_header Cache-Control "public, immutable";
}}
"""
        ssh_exec(client, f"""cat >> /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf << 'CONFEOF'
{static_block_alias}
CONFEOF""")
        print("Added static location to project conf")

        print("\n--- Restarting gateway ---")
        out, err = ssh_exec(client, "cd /home/ubuntu/gateway && docker compose down && docker compose up -d")
        print(f"Restart output: {out}")
        if err:
            print(f"Restart errors: {err}")

        time.sleep(5)

        print("\n--- Verifying nginx config ---")
        out, _ = ssh_exec(client, "docker exec gateway nginx -t 2>&1")
        print(out)

    print("\n--- Verifying URLs ---")
    time.sleep(2)
    
    out_files, _ = ssh_exec(client, f"ls /home/ubuntu/{DEPLOY_ID}/static/")
    print(f"Files in static dir: {out_files}")

    for f in out_files.split('\n'):
        f = f.strip()
        if f.endswith('.zip'):
            url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/static/{f}"
            out, _ = ssh_exec(client, f"curl -s -o /dev/null -w '%{{http_code}}' '{url}' --max-time 10")
            print(f"  {f}: HTTP {out}")

    client.close()


if __name__ == '__main__':
    main()
