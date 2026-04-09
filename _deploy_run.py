import paramiko
import sys
import os

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_PACKAGE = "deploy_package.tar.gz"

def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    print(f"Uploading {local_path} -> {remote_path} ...")
    sftp.put(local_path, remote_path)
    stat = sftp.stat(remote_path)
    print(f"Upload complete. Remote file size: {stat.st_size} bytes")
    sftp.close()

def run_command(client, cmd, timeout=300):
    print(f"\n{'='*60}")
    print(f"CMD: {cmd}")
    print('='*60)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print(f"STDERR: {err}")
    print(f"Exit code: {exit_code}")
    return exit_code, out, err

def main():
    print("=== Starting Deployment ===")
    print(f"Target: {HOST}:{REMOTE_DIR}")
    
    client = create_ssh_client()
    print("SSH connected.\n")

    # Step 1: Upload
    print("--- Step 1: Upload package ---")
    remote_package = f"{REMOTE_DIR}/{LOCAL_PACKAGE}"
    upload_file(client, LOCAL_PACKAGE, remote_package)

    # Step 2: Extract
    print("\n--- Step 2: Extract and rebuild ---")
    run_command(client, f"cd {REMOTE_DIR} && tar -xzf {LOCAL_PACKAGE} && rm {LOCAL_PACKAGE}")

    # Step 3: Build containers (no-cache for backend and h5-web only)
    print("\n--- Step 3: Build backend and h5-web containers ---")
    exit_code, out, err = run_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web",
        timeout=600
    )
    if exit_code != 0:
        print("BUILD FAILED! Full error above.")
        client.close()
        sys.exit(1)

    # Step 4: Restart containers
    print("\n--- Step 4: Restart backend and h5-web ---")
    run_command(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web")

    # Step 5: Wait and check status
    print("\n--- Step 5: Wait for startup and check status ---")
    run_command(client, "sleep 10")
    run_command(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps")

    # Step 6: Check backend logs
    print("\n--- Step 6: Backend logs ---")
    run_command(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml logs --tail=30 backend")

    # Step 7: Internal health check
    print("\n--- Step 7: Internal health check ---")
    container_name = f"{DEPLOY_ID}-backend"
    run_command(client, f"docker exec {container_name} curl -s http://localhost:8000/api/health || echo 'Health check via docker exec failed'")

    # Step 8: External health checks
    print("\n--- Step 8: External health checks ---")
    base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    
    run_command(client, f'curl -s -o /dev/null -w "HTTP %{{http_code}}" {base_url}/api/health')
    
    run_command(client, f'curl -s "{base_url}/api/health"')
    
    # Test source=voice parameter
    print("\n--- Step 9: Test search with source=voice ---")
    search_url = f"{base_url}/api/search?q=%E5%81%A5%E5%BA%B7&type=all&source=voice"
    run_command(client, f'curl -s "{search_url}" | python3 -m json.tool 2>/dev/null || curl -s "{search_url}"')

    # Test H5 homepage
    print("\n--- Step 10: Test H5 homepage ---")
    run_command(client, f'curl -s -o /dev/null -w "HTTP %{{http_code}}" {base_url}/')

    print("\n=== Deployment Complete ===")
    client.close()

if __name__ == "__main__":
    main()
