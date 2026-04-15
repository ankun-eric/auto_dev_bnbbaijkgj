import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USERNAME = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
STATIC_HOST_DIR = f"/home/ubuntu/{DEPLOY_ID}/static"


def ssh_exec(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err


def write_file_via_sftp(client, remote_path, content):
    sftp = client.open_sftp()
    with sftp.file(remote_path, 'w') as f:
        f.write(content)
    sftp.close()


def read_file_via_sftp(client, remote_path):
    sftp = client.open_sftp()
    with sftp.file(remote_path, 'r') as f:
        content = f.read().decode('utf-8')
    sftp.close()
    return content


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USERNAME, password=PASSWORD, timeout=30)
    print("Connected")

    # Step 1: Fix docker-compose.yml to add volume mount
    print("\n=== Step 1: Update gateway docker-compose.yml ===")
    dc_content = read_file_via_sftp(client, "/home/ubuntu/gateway/docker-compose.yml")
    print(f"Current:\n{dc_content}")

    volume_mount = f"      - {STATIC_HOST_DIR}:/data/static:ro"
    if STATIC_HOST_DIR not in dc_content:
        dc_content = dc_content.replace(
            "      - ./ssl:/etc/nginx/ssl:ro",
            f"      - ./ssl:/etc/nginx/ssl:ro\n{volume_mount}"
        )
        write_file_via_sftp(client, "/home/ubuntu/gateway/docker-compose.yml", dc_content)
        print(f"\nUpdated:\n{dc_content}")
    else:
        print("Volume mount already present")

    # Step 2: Fix nginx conf to add static location
    print("\n=== Step 2: Update project nginx conf ===")
    conf_path = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
    conf_content = read_file_via_sftp(client, conf_path)

    static_block = f"""
# Miniprogram zip static files
location /autodev/{DEPLOY_ID}/static/ {{
    alias /data/static/;
    autoindex off;
    expires 30d;
    add_header Cache-Control "public, immutable";
}}
"""

    if '/static/' not in conf_content or 'alias /data/static' not in conf_content:
        if '/static/' in conf_content:
            lines = conf_content.split('\n')
            cleaned = []
            skip = False
            for line in lines:
                if 'static' in line.lower() and 'location' in line.lower():
                    skip = True
                    continue
                if skip and line.strip() == '}':
                    skip = False
                    continue
                if not skip:
                    cleaned.append(line)
            conf_content = '\n'.join(cleaned)

        conf_content = conf_content.rstrip() + '\n' + static_block
        write_file_via_sftp(client, conf_path, conf_content)
        print("Added static location block")
    else:
        print("Static location already properly configured")

    print(f"Last 600 chars of conf:\n...{conf_content[-600:]}")

    # Step 3: Restart gateway
    print("\n=== Step 3: Restart gateway ===")
    ssh_exec(client, "cd /home/ubuntu/gateway && docker compose down 2>&1")
    print("Gateway stopped")
    time.sleep(2)

    # Reconnect other project containers to gateway network after it recreates
    out, err = ssh_exec(client, "cd /home/ubuntu/gateway && docker compose up -d 2>&1")
    print(f"Gateway started: {out} {err}")
    time.sleep(3)

    # Reconnect project containers to gateway-network
    print("\n=== Step 4: Reconnect project containers ===")
    containers = [
        f"{DEPLOY_ID}-backend",
        f"{DEPLOY_ID}-admin",
        f"{DEPLOY_ID}-h5",
    ]
    for c in containers:
        out, err = ssh_exec(client, f"docker network connect gateway-network {c} 2>&1")
        status = "connected" if "already" not in (out + err).lower() and not err else err or out
        print(f"  {c}: {status}")

    time.sleep(3)

    # Step 5: Verify
    print("\n=== Step 5: Verify nginx ===")
    out, err = ssh_exec(client, "docker exec gateway nginx -t 2>&1")
    print(f"nginx -t: {out} {err}")

    out, _ = ssh_exec(client, "docker exec gateway ls -la /data/static/ 2>&1")
    print(f"Container /data/static/: {out}")

    print("\n=== Step 6: Verify URLs ===")
    time.sleep(2)
    out_files, _ = ssh_exec(client, f"ls {STATIC_HOST_DIR}/")
    results = []
    for f in out_files.split('\n'):
        f = f.strip()
        if f.endswith('.zip'):
            url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/static/{f}"
            out, _ = ssh_exec(client, f"curl -s -o /dev/null -w '%{{http_code}}' '{url}' --max-time 10")
            print(f"  {f}: HTTP {out}")
            results.append((f, url, out))

    client.close()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    for name, url, code in results:
        print(f"  File: {name}")
        print(f"  URL:  {url}")
        print(f"  HTTP: {code}")
        print()


if __name__ == '__main__':
    main()
