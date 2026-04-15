import paramiko
import os
import sys
import zipfile
import datetime
import random
import time

HOST = "newbb.test.bangbangvip.com"
USERNAME = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_DIRS = {'node_modules', '.git', '__pycache__', '.vscode', '.idea'}
EXCLUDE_EXTS = {'.pyc', '.pyo'}


def generate_filename(prefix):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    hex_part = '%04x' % random.randint(0, 0xFFFF)
    return f"{prefix}_{ts}_{hex_part}.zip"


def create_zip(source_dir, zip_path):
    print(f"Creating zip: {zip_path}")
    print(f"Source: {source_dir}")
    count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if any(f.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                full_path = os.path.join(root, f)
                arcname = os.path.relpath(full_path, os.path.dirname(source_dir))
                zf.write(full_path, arcname)
                count += 1
    size_kb = os.path.getsize(zip_path) / 1024
    print(f"  Packed {count} files, size: {size_kb:.1f} KB")
    return zip_path


def ssh_exec(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err


def main():
    miniprogram_name = generate_filename("miniprogram")
    verify_name = generate_filename("verify_miniprogram")

    miniprogram_dir = os.path.join(PROJECT_ROOT, "miniprogram")
    verify_dir = os.path.join(PROJECT_ROOT, "verify-miniprogram")
    output_dir = os.path.join(PROJECT_ROOT, "_deploy_tmp")

    miniprogram_zip = os.path.join(output_dir, miniprogram_name)
    verify_zip = os.path.join(output_dir, verify_name)

    print("=" * 60)
    print("Step 1: Creating zip archives")
    print("=" * 60)
    create_zip(miniprogram_dir, miniprogram_zip)
    create_zip(verify_dir, verify_zip)

    print("\n" + "=" * 60)
    print("Step 2: Connecting to server")
    print("=" * 60)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USERNAME, password=PASSWORD, timeout=30)
    print("Connected to server")

    remote_static_dir = f"/home/ubuntu/{DEPLOY_ID}/static"
    ssh_exec(client, f"mkdir -p {remote_static_dir}")
    print(f"Ensured remote dir: {remote_static_dir}")

    print("\n" + "=" * 60)
    print("Step 3: Uploading zip files")
    print("=" * 60)
    sftp = client.open_sftp()

    for local_path, name in [(miniprogram_zip, miniprogram_name), (verify_zip, verify_name)]:
        remote_path = f"{remote_static_dir}/{name}"
        print(f"Uploading {name} ...")
        sftp.put(local_path, remote_path)
        stat = sftp.stat(remote_path)
        print(f"  Uploaded: {stat.st_size} bytes")

    sftp.close()

    print("\n" + "=" * 60)
    print("Step 4: Checking gateway nginx config")
    print("=" * 60)

    out, err = ssh_exec(client, "ls /home/ubuntu/gateway/")
    print(f"Gateway dir: {out}")

    static_location = f"autodev/{DEPLOY_ID}/static/"
    out, err = ssh_exec(client, f"grep -r '{static_location}' /home/ubuntu/gateway/ 2>/dev/null || echo 'NOT_FOUND'")
    
    if "NOT_FOUND" in out or not out.strip():
        print("Static location not found in gateway config. Adding it...")
        
        out2, _ = ssh_exec(client, "ls /home/ubuntu/gateway/conf.d/ 2>/dev/null || ls /home/ubuntu/gateway/ 2>/dev/null")
        print(f"Config files: {out2}")

        routes_file = f"/home/ubuntu/{DEPLOY_ID}/gateway-routes.conf"
        out3, _ = ssh_exec(client, f"test -f {routes_file} && echo EXISTS || echo MISSING")
        print(f"Routes file: {out3}")

        static_block = f"""
# 小程序 zip 静态文件
location /autodev/{DEPLOY_ID}/static/ {{
    alias /home/ubuntu/{DEPLOY_ID}/static/;
    autoindex off;
    expires 30d;
    add_header Cache-Control "public, immutable";
}}
"""
        if out3.strip() == "EXISTS":
            out_check, _ = ssh_exec(client, f"grep 'static/' {routes_file} || echo 'NOT_IN_FILE'")
            if "NOT_IN_FILE" in out_check:
                escaped_block = static_block.replace("'", "'\\''")
                ssh_exec(client, f"echo '{escaped_block}' >> {routes_file}")
                print("Added static location to gateway-routes.conf")
            else:
                print("Static location already in routes file")
        
        gateway_conf_files = [
            "/home/ubuntu/gateway/conf.d/default.conf",
            "/home/ubuntu/gateway/nginx.conf",
        ]
        for gf in gateway_conf_files:
            out_gf, _ = ssh_exec(client, f"test -f {gf} && echo EXISTS || echo MISSING")
            if out_gf.strip() == "EXISTS":
                print(f"Found gateway config: {gf}")

        out_docker, _ = ssh_exec(client, "docker ps --format '{{.Names}}' | grep gateway")
        print(f"Gateway container: {out_docker}")

        if out_docker.strip():
            gateway_container = out_docker.strip().split('\n')[0]
            
            out_inc, _ = ssh_exec(client, f"docker exec {gateway_container} cat /etc/nginx/nginx.conf 2>/dev/null | grep include || echo 'NO_INCLUDE'")
            print(f"Nginx includes: {out_inc}")

            out_grep_static, _ = ssh_exec(client, f"docker exec {gateway_container} grep -r 'static' /etc/nginx/conf.d/ 2>/dev/null || echo 'NO_STATIC'")
            print(f"Existing static configs: {out_grep_static}")

            out_vol, _ = ssh_exec(client, f"docker inspect {gateway_container} --format '{{{{json .Mounts}}}}' 2>/dev/null")
            print(f"Gateway mounts: {out_vol[:500]}")

            static_nginx_conf = f"""
location /autodev/{DEPLOY_ID}/static/ {{
    alias /home/ubuntu/{DEPLOY_ID}/static/;
    autoindex off;
    expires 30d;
    add_header Cache-Control "public, immutable";
}}
"""
            out_existing, _ = ssh_exec(client, f"docker exec {gateway_container} grep '{DEPLOY_ID}/static' /etc/nginx/conf.d/*.conf 2>/dev/null || echo 'NOT_FOUND'")
            if "NOT_FOUND" in out_existing:
                temp_conf = f"/tmp/static_{DEPLOY_ID}.conf"
                ssh_exec(client, f"""cat > {temp_conf} << 'CONFEOF'
{static_nginx_conf}
CONFEOF""")
                
                out_dc, _ = ssh_exec(client, "ls /home/ubuntu/gateway/docker-compose*.yml 2>/dev/null || ls /home/ubuntu/docker-compose*.yml 2>/dev/null")
                print(f"Docker compose files: {out_dc}")

                out_routes_mount, _ = ssh_exec(client, f"docker exec {gateway_container} ls /etc/nginx/conf.d/ 2>/dev/null")
                print(f"Nginx conf.d contents: {out_routes_mount}")

                out_find_route, _ = ssh_exec(client, f"docker exec {gateway_container} grep -l '{DEPLOY_ID}' /etc/nginx/conf.d/*.conf 2>/dev/null || echo 'NOT_FOUND'")
                print(f"File containing project routes: {out_find_route}")

                if out_find_route.strip() != "NOT_FOUND":
                    route_file_in_container = out_find_route.strip().split('\n')[0]
                    out_check2, _ = ssh_exec(client, f"docker exec {gateway_container} grep 'static/' {route_file_in_container} 2>/dev/null || echo 'NOT_IN_FILE'")
                    if "NOT_IN_FILE" in out_check2:
                        host_routes, _ = ssh_exec(client, f"docker inspect {gateway_container} --format '{{{{range .Mounts}}}}{{{{.Source}}}}:{{{{.Destination}}}} {{{{end}}}}' 2>/dev/null")
                        print(f"Mount mappings: {host_routes}")

                        host_route_file = None
                        for mount_pair in host_routes.split():
                            if ':' in mount_pair:
                                src, dst = mount_pair.split(':', 1)
                                if route_file_in_container.startswith(dst) or dst in route_file_in_container:
                                    relative = route_file_in_container.replace(dst, '')
                                    host_route_file = src + relative
                                    break
                        
                        if not host_route_file:
                            host_route_file = f"/home/ubuntu/{DEPLOY_ID}/gateway-routes.conf"
                            out_test, _ = ssh_exec(client, f"test -f {host_route_file} && echo YES || echo NO")
                            if out_test.strip() != "YES":
                                host_route_file = None

                        if host_route_file:
                            print(f"Appending static block to {host_route_file}")
                            escaped = static_nginx_conf.replace("'", "'\\''")
                            cmd = f"""cat >> {host_route_file} << 'STATICEOF'
{static_nginx_conf}
STATICEOF"""
                            ssh_exec(client, cmd)
                            print("Reloading nginx...")
                            ssh_exec(client, f"docker exec {gateway_container} nginx -t 2>&1")
                            ssh_exec(client, f"docker exec {gateway_container} nginx -s reload 2>&1")
                            print("Nginx reloaded")
                        else:
                            print("Could not find host route file, trying direct approach...")
                            cmd = f"""docker exec {gateway_container} sh -c 'cat >> {route_file_in_container} << STATICEOF
{static_nginx_conf}
STATICEOF'"""
                            ssh_exec(client, cmd)
                            ssh_exec(client, f"docker exec {gateway_container} nginx -t 2>&1")
                            ssh_exec(client, f"docker exec {gateway_container} nginx -s reload 2>&1")
                            print("Nginx reloaded (direct)")
                    else:
                        print("Static location already configured in container")
                else:
                    print("Project routes not found in container, trying to find config...")
                    cmd = f"""docker exec {gateway_container} sh -c 'for f in /etc/nginx/conf.d/*.conf; do echo "=== $f ==="; grep -l "autodev" "$f" 2>/dev/null; done'"""
                    out_scan, _ = ssh_exec(client, cmd)
                    print(f"Config scan: {out_scan}")
            else:
                print("Static location already configured")
    else:
        print(f"Static location already exists: {out}")

    print("\n" + "=" * 60)
    print("Step 5: Verifying access")
    print("=" * 60)

    time.sleep(2)

    miniprogram_url = f"{BASE_URL}/static/{miniprogram_name}"
    verify_url = f"{BASE_URL}/static/{verify_name}"

    for url, name in [(miniprogram_url, miniprogram_name), (verify_url, verify_name)]:
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' '{url}' --max-time 10"
        out, err = ssh_exec(client, cmd)
        print(f"{name}: HTTP {out}")

    client.close()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"主小程序 zip: {miniprogram_name}")
    print(f"  URL: {miniprogram_url}")
    print(f"验证小程序 zip: {verify_name}")
    print(f"  URL: {verify_url}")

    os.remove(miniprogram_zip)
    os.remove(verify_zip)
    print("\nLocal temp zip files cleaned up.")


if __name__ == '__main__':
    main()
