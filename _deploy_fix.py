"""Fix deployment: upload package.json and rebuild h5-web."""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PROJECT_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def run_ssh(client, cmd, timeout=600):
    print(f"[SSH] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        last = out[-3000:] if len(out) > 3000 else out
        print(last)
    if err.strip() and exit_code != 0:
        print(f"[STDERR] {err[-1000:]}")
    return exit_code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    print("Connected!")

    # Force reset the git repo to get clean state
    print("\n=== Force resetting git repo ===")
    run_ssh(client, f"cd {PROJECT_DIR} && git checkout -- . && git clean -fd 2>&1", timeout=60)
    run_ssh(client, f"cd {PROJECT_DIR} && git pull origin master --force 2>&1", timeout=120)

    # Upload modified files
    print("\n=== Uploading modified files ===")
    import os
    sftp = client.open_sftp()
    local_base = os.path.dirname(os.path.abspath(__file__))
    
    files_to_upload = [
        "h5-web/src/app/(tabs)/home/page.tsx",
        "h5-web/src/lib/useHomeConfig.ts",
        "h5-web/package.json",
        "flutter_app/lib/screens/home/home_screen.dart",
        "miniprogram/pages/home/index.js",
        "miniprogram/pages/home/index.wxml",
        "backend/app/api/home_config.py",
        "backend/app/init_data.py",
        "docker-compose.prod.yml",
        "tests/test_search_placeholder_config.py",
    ]

    for f in files_to_upload:
        local_path = os.path.join(local_base, f)
        remote_path = f"{PROJECT_DIR}/{f}"
        if os.path.exists(local_path):
            try:
                sftp.put(local_path, remote_path)
                print(f"  OK: {f}")
            except Exception as e:
                print(f"  FAIL: {f} -> {e}")
    sftp.close()

    # Rebuild backend and h5-web
    print("\n=== Building backend ===")
    code, _, _ = run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1", timeout=300)
    print(f"Backend build exit code: {code}")

    print("\n=== Building h5-web ===")
    code, _, _ = run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1", timeout=300)
    print(f"H5-web build exit code: {code}")

    # Restart all services
    print("\n=== Restarting services ===")
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)

    print("\nWaiting 15s for services...")
    time.sleep(15)

    # Check status
    print("\n=== Container Status ===")
    run_ssh(client, "docker ps --filter 'name=3b7b999d' --format '{{.Names}} {{.Status}}'")

    # Test API
    print("\n=== Testing API ===")
    code, out, _ = run_ssh(client, "curl -s https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api/home-config")
    print(f"home-config response: {out[:500]}")

    # Test H5
    print("\n=== Testing H5 ===")
    code, out, _ = run_ssh(client, "curl -s -o /dev/null -w '%{http_code}' https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/")

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
