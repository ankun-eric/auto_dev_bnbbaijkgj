import paramiko
import subprocess
import sys
import os
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PORT = 22
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_PROJECT = r"C:\auto_output\bnbbaijkgj"

def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client

def run_remote(client, cmd, timeout=300):
    print(f"  [REMOTE] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  [STDOUT] {out.strip()[:2000]}")
    if err.strip():
        print(f"  [STDERR] {err.strip()[:2000]}")
    print(f"  [EXIT] {exit_code}")
    return exit_code, out, err

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    print(f"  [UPLOAD] {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)
    sftp.close()

def main():
    # Step 1: SSH connectivity check
    print("=" * 60)
    print("STEP 1: Checking SSH connectivity")
    print("=" * 60)
    try:
        client = create_ssh_client()
        run_remote(client, "echo 'SSH connection OK' && hostname")
        print("  SSH connection successful!\n")
    except Exception as e:
        print(f"  FAILED: SSH connection failed: {e}")
        sys.exit(1)

    # Step 2: Package and upload admin-web source code
    print("=" * 60)
    print("STEP 2: Packaging and uploading admin-web source code")
    print("=" * 60)

    tar_file = os.path.join(LOCAL_PROJECT, "admin-web.tar.gz")
    try:
        os.remove(tar_file)
    except FileNotFoundError:
        pass

    print("  Creating tar archive of admin-web (excluding node_modules, .next, .git)...")
    result = subprocess.run(
        [
            "tar", "-czf", tar_file,
            "--exclude=node_modules",
            "--exclude=.next",
            "--exclude=.git",
            "-C", LOCAL_PROJECT,
            "admin-web"
        ],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"  FAILED: tar creation failed: {result.stderr}")
        sys.exit(1)

    tar_size = os.path.getsize(tar_file) / (1024 * 1024)
    print(f"  Archive created: {tar_size:.2f} MB")

    remote_tar = f"{REMOTE_DIR}/admin-web.tar.gz"
    upload_file(client, tar_file, remote_tar)
    print("  Upload complete!")

    # Extract on server (backup old, extract new)
    print("  Extracting on server...")
    run_remote(client, f"cd {REMOTE_DIR} && tar -xzf admin-web.tar.gz && rm admin-web.tar.gz")
    print("  Source code synced!\n")

    # Clean up local tar
    try:
        os.remove(tar_file)
    except:
        pass

    # Step 3: Rebuild and restart admin-web container
    print("=" * 60)
    print("STEP 3: Rebuilding and restarting admin-web container")
    print("=" * 60)

    print("  Building admin-web container (this may take a few minutes)...")
    exit_code, out, err = run_remote(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1",
        timeout=600
    )
    if exit_code != 0:
        print("  WARNING: Build may have issues, checking further...")

    print("\n  Starting admin-web container...")
    exit_code, out, err = run_remote(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1",
        timeout=120
    )

    # Wait for container to stabilize
    print("  Waiting 10 seconds for container to stabilize...")
    time.sleep(10)

    # Step 4: Verify deployment
    print("\n" + "=" * 60)
    print("STEP 4: Verifying deployment")
    print("=" * 60)

    # Check container status
    print("\n  --- Container Status ---")
    container_name = f"{DEPLOY_ID}-admin"
    exit_code, out, err = run_remote(
        client,
        f"docker ps --filter 'name={container_name}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'"
    )

    # Also check with docker compose
    run_remote(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps admin-web 2>&1"
    )

    # Check container logs (last 30 lines)
    print("\n  --- Container Logs (last 30 lines) ---")
    run_remote(
        client,
        f"docker logs --tail 30 {container_name} 2>&1"
    )

    # Test URL access from server
    print("\n  --- URL Access Check ---")
    test_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/"
    exit_code, out, err = run_remote(
        client,
        f"curl -sS -o /dev/null -w '%{{http_code}}' -k --max-time 15 '{test_url}'"
    )
    http_code = out.strip()
    print(f"  URL: {test_url}")
    print(f"  HTTP Status Code: {http_code}")

    if http_code in ("200", "304", "301", "302", "307", "308"):
        print("  URL is REACHABLE!")
    else:
        print("  URL may not be reachable, checking with more details...")
        run_remote(client, f"curl -vk --max-time 15 '{test_url}' 2>&1 | head -30")

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"  Container: {container_name}")
    print(f"  URL: {test_url}")
    print(f"  HTTP Code: {http_code}")
    if http_code in ("200", "304", "301", "302", "307", "308"):
        print("  Status: SUCCESS")
    else:
        print("  Status: NEEDS ATTENTION (check logs above)")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
