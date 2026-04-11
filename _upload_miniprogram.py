#!/usr/bin/env python3
import os
import sys
import zipfile
import random
import string
import datetime
import paramiko
import urllib.request
import ssl
import time

MINIPROGRAM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniprogram")
EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".DS_Store"}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo"}

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PROJECT_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_BASE = f"/home/ubuntu/{PROJECT_ID}"
REMOTE_DIR = f"{REMOTE_BASE}/static-downloads"

PROD_DOMAIN = "newbb.bangbangvip.com"
TEST_DOMAIN = "newbb.test.bangbangvip.com"
URL_PATH_PREFIX = f"/autodev/{PROJECT_ID}"


def generate_filename():
    now = datetime.datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    rand_hex = ''.join(random.choices('0123456789abcdef', k=4))
    return f"miniprogram_{ts}_{rand_hex}.zip"


def create_zip(source_dir, zip_path):
    print(f"Creating zip: {zip_path}")
    count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if os.path.splitext(f)[1] in EXCLUDE_EXTENSIONS:
                    continue
                if f in EXCLUDE_DIRS:
                    continue
                full_path = os.path.join(root, f)
                arcname = os.path.join("miniprogram", os.path.relpath(full_path, source_dir))
                zf.write(full_path, arcname)
                count += 1
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"Zip created: {count} files, {size_mb:.2f} MB")
    return zip_path


def upload_sftp(local_path, remote_path):
    print(f"Connecting to {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    print(f"Ensuring remote directory exists: {REMOTE_DIR}")
    ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
    time.sleep(1)

    sftp = ssh.open_sftp()
    print(f"Uploading {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)

    remote_size = sftp.stat(remote_path).st_size
    local_size = os.path.getsize(local_path)
    print(f"Upload complete. Local: {local_size} bytes, Remote: {remote_size} bytes")
    assert remote_size == local_size, "Size mismatch!"

    sftp.close()
    return ssh


def check_nginx_config(ssh):
    print("\nChecking nginx configuration for static file serving...")

    search_cmd = f"grep -r 'static-downloads' /etc/nginx/ 2>/dev/null || echo 'NOT_FOUND'"
    stdin, stdout, stderr = ssh.exec_command(search_cmd)
    result = stdout.read().decode().strip()
    print(f"Grep result: {result}")

    if result and "NOT_FOUND" not in result:
        print("Static file serving already configured in nginx.")
        return True

    search_cmd2 = f"grep -rl '{PROJECT_ID}' /etc/nginx/ 2>/dev/null || echo 'NOT_FOUND'"
    stdin, stdout, stderr = ssh.exec_command(search_cmd2)
    config_files = stdout.read().decode().strip()
    print(f"Config files with project ID: {config_files}")

    if config_files and "NOT_FOUND" not in config_files:
        config_file = config_files.split('\n')[0].strip()
        print(f"Found existing config: {config_file}")

        stdin, stdout, stderr = ssh.exec_command(f"cat {config_file}")
        config_content = stdout.read().decode()
        print(f"Current config:\n{config_content[:2000]}")

        if "static-downloads" in config_content:
            print("Static downloads already configured.")
            return True

        location_block = f"""
    # Static file downloads for miniprogram packages
    location {URL_PATH_PREFIX}/static-downloads/ {{
        alias {REMOTE_DIR}/;
        autoindex off;
        add_header Content-Disposition 'attachment';
        add_header Access-Control-Allow-Origin *;
    }}
"""
        # We need to find the right place to insert
        # Look for the server block that contains our project and add before the last }
        # Instead, let's add a new location block inside the existing server block
        
        # Use a sed approach: insert before the last closing brace of the relevant server block
        # But safer: just find location blocks for our project and add alongside
        
        # Write a temp config snippet and include it
        temp_conf = f"/tmp/static_downloads_{PROJECT_ID[:8]}.conf"
        write_cmd = f"""cat > {temp_conf} << 'CONFEOF'
{location_block}
CONFEOF"""
        ssh.exec_command(write_cmd)
        time.sleep(0.5)

        # Try to insert the location block into the existing config
        # Find the line with the last } in the server block for our project
        # A safer approach: use sed to insert before a known pattern
        
        # Let's check if there's a location block for our project path
        insert_marker = f"location {URL_PATH_PREFIX}"
        if insert_marker in config_content or f"location /{PROJECT_ID}" in config_content or f"location /autodev/{PROJECT_ID}" in config_content:
            # Insert after the first location block for our project
            # Use Python to manipulate the config
            lines = config_content.split('\n')
            new_lines = []
            inserted = False
            brace_count = 0
            in_our_location = False
            
            for i, line in enumerate(lines):
                new_lines.append(line)
                if not inserted and URL_PATH_PREFIX in line and 'location' in line and 'static-downloads' not in line:
                    in_our_location = True
                if in_our_location:
                    brace_count += line.count('{') - line.count('}')
                    if brace_count <= 0 and in_our_location:
                        new_lines.append(location_block)
                        inserted = True
                        in_our_location = False

            if not inserted:
                # Fallback: insert before the very last }
                for i in range(len(new_lines) - 1, -1, -1):
                    if new_lines[i].strip() == '}':
                        new_lines.insert(i, location_block)
                        inserted = True
                        break

            if inserted:
                new_config = '\n'.join(new_lines)
                escaped = new_config.replace("'", "'\\''")
                write_cmd = f"echo '{escaped}' | sudo tee {config_file} > /dev/null"
                # Safer: write to temp then move
                tmp_file = f"/tmp/nginx_updated_{PROJECT_ID[:8]}.conf"
                sftp_ssh = ssh.open_sftp()
                with sftp_ssh.file(tmp_file, 'w') as f:
                    f.write(new_config)
                sftp_ssh.close()

                ssh.exec_command(f"sudo cp {config_file} {config_file}.bak")
                time.sleep(0.5)
                ssh.exec_command(f"sudo cp {tmp_file} {config_file}")
                time.sleep(0.5)

                # Test nginx config
                stdin, stdout, stderr = ssh.exec_command("sudo nginx -t 2>&1")
                test_result = stdout.read().decode() + stderr.read().decode()
                print(f"Nginx test: {test_result}")

                if "successful" in test_result:
                    ssh.exec_command("sudo nginx -s reload")
                    time.sleep(1)
                    print("Nginx reloaded successfully.")
                    return True
                else:
                    print("Nginx config test failed! Restoring backup...")
                    ssh.exec_command(f"sudo cp {config_file}.bak {config_file}")
                    ssh.exec_command("sudo nginx -s reload")
                    return False
        else:
            print(f"Could not find location block for {URL_PATH_PREFIX}, attempting direct insertion...")
            # Find server block and insert
            lines = config_content.split('\n')
            new_lines = []
            inserted = False
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == '}' and not inserted:
                    lines.insert(i, location_block)
                    inserted = True
                    break
            
            if inserted:
                new_config = '\n'.join(lines)
                tmp_file = f"/tmp/nginx_updated_{PROJECT_ID[:8]}.conf"
                sftp_ssh = ssh.open_sftp()
                with sftp_ssh.file(tmp_file, 'w') as f:
                    f.write(new_config)
                sftp_ssh.close()
                
                ssh.exec_command(f"sudo cp {config_file} {config_file}.bak")
                time.sleep(0.5)
                ssh.exec_command(f"sudo cp {tmp_file} {config_file}")
                time.sleep(0.5)
                
                stdin, stdout, stderr = ssh.exec_command("sudo nginx -t 2>&1")
                test_result = stdout.read().decode() + stderr.read().decode()
                print(f"Nginx test: {test_result}")
                
                if "successful" in test_result:
                    ssh.exec_command("sudo nginx -s reload")
                    time.sleep(1)
                    print("Nginx reloaded successfully.")
                    return True
                else:
                    print("Nginx config test failed! Restoring backup...")
                    ssh.exec_command(f"sudo cp {config_file}.bak {config_file}")
                    ssh.exec_command("sudo nginx -s reload")
                    return False

    else:
        print("No existing nginx config found for this project. Creating new config...")
        new_config = f"""server {{
    listen 80;
    server_name {TEST_DOMAIN};
    
    location {URL_PATH_PREFIX}/static-downloads/ {{
        alias {REMOTE_DIR}/;
        autoindex off;
        add_header Content-Disposition 'attachment';
        add_header Access-Control-Allow-Origin *;
    }}
}}
"""
        config_file = f"/etc/nginx/conf.d/static-downloads-{PROJECT_ID[:8]}.conf"
        tmp_file = f"/tmp/nginx_static_{PROJECT_ID[:8]}.conf"
        sftp_ssh = ssh.open_sftp()
        with sftp_ssh.file(tmp_file, 'w') as f:
            f.write(new_config)
        sftp_ssh.close()

        ssh.exec_command(f"sudo cp {tmp_file} {config_file}")
        time.sleep(0.5)

        stdin, stdout, stderr = ssh.exec_command("sudo nginx -t 2>&1")
        test_result = stdout.read().decode() + stderr.read().decode()
        print(f"Nginx test: {test_result}")

        if "successful" in test_result:
            ssh.exec_command("sudo nginx -s reload")
            time.sleep(1)
            print("Nginx reloaded successfully.")
            return True
        else:
            print("Nginx config test failed! Removing new config...")
            ssh.exec_command(f"sudo rm {config_file}")
            ssh.exec_command("sudo nginx -s reload")
            return False

    return False


def verify_url(filename):
    results = {}
    for domain in [TEST_DOMAIN, PROD_DOMAIN]:
        url = f"https://{domain}{URL_PATH_PREFIX}/static-downloads/{filename}"
        print(f"\nVerifying: {url}")
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, method='HEAD')
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            print(f"  Status: {resp.status}")
            print(f"  Content-Length: {resp.headers.get('Content-Length', 'unknown')}")
            results[domain] = True
        except Exception as e:
            print(f"  Error: {e}")
            # Try GET as fallback (some servers don't support HEAD)
            try:
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=15, context=ctx)
                print(f"  GET Status: {resp.status}")
                results[domain] = True
            except Exception as e2:
                print(f"  GET also failed: {e2}")
                results[domain] = False
    return results


def verify_url_via_ssh(ssh, filename):
    """Verify by checking the file directly and via curl on the server."""
    print(f"\nVerifying file exists on server...")
    remote_path = f"{REMOTE_DIR}/{filename}"
    stdin, stdout, stderr = ssh.exec_command(f"ls -la {remote_path}")
    result = stdout.read().decode().strip()
    print(f"  File check: {result}")
    
    for domain in [TEST_DOMAIN, PROD_DOMAIN]:
        url = f"https://{domain}{URL_PATH_PREFIX}/static-downloads/{filename}"
        print(f"\nServer-side curl: {url}")
        stdin, stdout, stderr = ssh.exec_command(f"curl -sSI -k --max-time 10 '{url}' 2>&1 | head -20")
        result = stdout.read().decode().strip()
        print(f"  {result}")
    
    # Also try via the location that might be configured differently
    for domain in [TEST_DOMAIN, PROD_DOMAIN]:
        url = f"https://{domain}{URL_PATH_PREFIX}/{filename}"
        print(f"\nAlternate URL check: {url}")
        stdin, stdout, stderr = ssh.exec_command(f"curl -sSI -k --max-time 10 '{url}' 2>&1 | head -5")
        result = stdout.read().decode().strip()
        print(f"  {result}")


def main():
    filename = generate_filename()
    print(f"=== Filename: {filename} ===\n")

    local_zip = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    create_zip(MINIPROGRAM_DIR, local_zip)

    remote_path = f"{REMOTE_DIR}/{filename}"
    ssh = upload_sftp(local_zip, remote_path)

    nginx_ok = check_nginx_config(ssh)
    print(f"\nNginx configuration: {'OK' if nginx_ok else 'NEEDS ATTENTION'}")

    verify_url_via_ssh(ssh, filename)
    
    print("\nVerifying from this machine...")
    url_results = verify_url(filename)

    ssh.close()

    # Cleanup local zip
    if os.path.exists(local_zip):
        os.remove(local_zip)
        print(f"\nCleaned up local zip: {local_zip}")

    prod_url = f"https://{PROD_DOMAIN}{URL_PATH_PREFIX}/static-downloads/{filename}"
    test_url = f"https://{TEST_DOMAIN}{URL_PATH_PREFIX}/static-downloads/{filename}"

    print("\n" + "=" * 60)
    print(f"FILENAME: {filename}")
    print(f"DOWNLOAD URL (prod): {prod_url}")
    print(f"DOWNLOAD URL (test): {test_url}")
    print(f"PROD URL verified: {url_results.get(PROD_DOMAIN, False)}")
    print(f"TEST URL verified: {url_results.get(TEST_DOMAIN, False)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
