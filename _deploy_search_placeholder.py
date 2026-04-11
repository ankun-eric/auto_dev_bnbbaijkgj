"""Deploy script for search placeholder config feature."""
import paramiko
import sys
import time
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PROJECT_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REPO_URL = "https://ankun-eric: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@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"


def run_ssh(client, cmd, timeout=300):
    print(f"[SSH] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out[-2000:] if len(out) > 2000 else out)
    if err.strip():
        print(f"[STDERR] {err[-1000:]}" if len(err) > 1000 else f"[STDERR] {err}")
    return exit_code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    print("Connected!")

    # Check if project dir exists
    code, out, _ = run_ssh(client, f"test -d {PROJECT_DIR} && echo EXISTS || echo NOT_EXISTS")
    if "NOT_EXISTS" in out:
        print("Project not found, cloning...")
        run_ssh(client, f"git clone {REPO_URL} {PROJECT_DIR}", timeout=120)
    else:
        print("Project exists, pulling latest...")
        run_ssh(client, f"cd {PROJECT_DIR} && git stash 2>/dev/null; git pull origin master --force", timeout=120)

    # Sync local changes to server using rsync-like approach via SFTP
    print("Uploading modified files via SFTP...")
    sftp = client.open_sftp()
    
    files_to_upload = [
        ("h5-web/src/app/(tabs)/home/page.tsx", f"{PROJECT_DIR}/h5-web/src/app/(tabs)/home/page.tsx"),
        ("h5-web/src/lib/useHomeConfig.ts", f"{PROJECT_DIR}/h5-web/src/lib/useHomeConfig.ts"),
        ("flutter_app/lib/screens/home/home_screen.dart", f"{PROJECT_DIR}/flutter_app/lib/screens/home/home_screen.dart"),
        ("miniprogram/pages/home/index.js", f"{PROJECT_DIR}/miniprogram/pages/home/index.js"),
        ("miniprogram/pages/home/index.wxml", f"{PROJECT_DIR}/miniprogram/pages/home/index.wxml"),
        ("backend/app/api/home_config.py", f"{PROJECT_DIR}/backend/app/api/home_config.py"),
        ("backend/app/init_data.py", f"{PROJECT_DIR}/backend/app/init_data.py"),
        ("docker-compose.prod.yml", f"{PROJECT_DIR}/docker-compose.prod.yml"),
        ("tests/test_search_placeholder_config.py", f"{PROJECT_DIR}/tests/test_search_placeholder_config.py"),
    ]
    
    local_base = os.path.dirname(os.path.abspath(__file__))
    for local_rel, remote_path in files_to_upload:
        local_path = os.path.join(local_base, local_rel)
        if os.path.exists(local_path):
            try:
                sftp.put(local_path, remote_path)
                print(f"  Uploaded: {local_rel}")
            except Exception as e:
                print(f"  Failed {local_rel}: {e}")
    sftp.close()

    # Build and deploy with docker-compose
    print("\nRebuilding and deploying containers...")
    code, out, err = run_ssh(
        client,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web 2>&1",
        timeout=600
    )
    if code != 0:
        print(f"Build failed with code {code}")
        # Try without --no-cache
        print("Retrying build without --no-cache...")
        code, out, err = run_ssh(
            client,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend h5-web 2>&1",
            timeout=600
        )

    print("\nRestarting containers...")
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)

    # Wait for services to start
    print("\nWaiting 15 seconds for services to start...")
    time.sleep(15)

    # Check container status
    print("\nChecking container status...")
    run_ssh(client, f"docker ps --filter 'name=3b7b999d' --format '{{{{.Names}}}} {{{{.Status}}}}'")

    # Verify API endpoint
    print("\nVerifying API...")
    code, out, _ = run_ssh(
        client,
        "curl -s -o /dev/null -w '%{http_code}' https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api/home-config"
    )
    
    if "200" in out:
        print("API endpoint is healthy!")
    else:
        print(f"API returned: {out}")
        # Check logs
        print("\nChecking backend logs...")
        run_ssh(client, f"docker logs 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend --tail 30 2>&1")

    # Verify search_placeholder value from API
    print("\nVerifying search_placeholder from API...")
    code, out, _ = run_ssh(
        client,
        "curl -s https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api/home-config"
    )
    print(f"API response: {out[:500]}")

    client.close()
    print("\nDeployment complete!")


if __name__ == "__main__":
    main()
