import paramiko
import time
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
PROJECT_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
COMPOSE_FILE = "docker-compose.prod.yml"

def run_ssh_command(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT CODE] {exit_code}")
    return exit_code, out, err

def main():
    print("=" * 60)
    print("Connecting to server:", HOST)
    print("=" * 60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    print("Connected successfully!")

    # Step 1: Fetch and reset to latest
    print("\n" + "=" * 60)
    print("STEP 1: Git fetch and reset")
    print("=" * 60)
    run_ssh_command(ssh, f"cd {PROJECT_DIR} && git fetch origin master")
    run_ssh_command(ssh, f"cd {PROJECT_DIR} && git reset --hard origin/master")

    # Step 2: Build containers
    print("\n" + "=" * 60)
    print("STEP 2: Docker build (backend + h5-web)")
    print("=" * 60)
    exit_code, out, err = run_ssh_command(
        ssh,
        f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache backend h5-web",
        timeout=600,
    )
    if exit_code != 0:
        print("\n!!! BUILD FAILED - checking for missing module issues !!!")
        combined = out + err
        if "html5-qrcode" in combined or "qrcode.react" in combined or "Module not found" in combined:
            print("Detected missing module error - checking scan page files...")
            code, scan_out, _ = run_ssh_command(
                ssh,
                f"find {PROJECT_DIR}/h5-web/src -name '*.tsx' -path '*/scan/*' -o -name '*.tsx' -path '*/checkup/*' | head -20"
            )
            print(f"Scan-related files found:\n{scan_out}")
            code2, pkg_out, _ = run_ssh_command(
                ssh,
                f"cd {PROJECT_DIR}/h5-web && cat package.json | python3 -c \"import sys,json; d=json.load(sys.stdin); deps=d.get('dependencies',{{}}); print('html5-qrcode' in deps, 'qrcode.react' in deps)\""
            )
            print(f"Package deps check: {pkg_out.strip()}")
            print("Attempting rebuild after investigation...")
            exit_code, out, err = run_ssh_command(
                ssh,
                f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache backend h5-web",
                timeout=600,
            )
            if exit_code != 0:
                print("BUILD STILL FAILED. Exiting.")
                ssh.close()
                sys.exit(1)
        else:
            print("Build failed for unknown reason. Exiting.")
            ssh.close()
            sys.exit(1)

    # Step 3: Start containers
    print("\n" + "=" * 60)
    print("STEP 3: Docker compose up")
    print("=" * 60)
    run_ssh_command(ssh, f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d")

    # Step 4: Wait
    print("\n" + "=" * 60)
    print("STEP 4: Waiting 15 seconds for containers to start...")
    print("=" * 60)
    time.sleep(15)

    # Step 5: Check container status
    print("\n" + "=" * 60)
    print("STEP 5: Container status")
    print("=" * 60)
    _, container_status, _ = run_ssh_command(ssh, "docker ps --filter 'name=3b7b999d'")

    # Step 6: Health checks
    print("\n" + "=" * 60)
    print("STEP 6: Health checks")
    print("=" * 60)
    _, api_response, _ = run_ssh_command(
        ssh,
        f"curl -s {BASE_URL}/api/home-config"
    )
    _, h5_status, _ = run_ssh_command(
        ssh,
        f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/"
    )

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"Container status:\n{container_status.strip()}")
    print(f"\nAPI response (/api/home-config):\n{api_response.strip()}")
    print(f"\nH5 web HTTP status: {h5_status.strip()}")

    api_ok = "search_placeholder" in api_response or '"code"' in api_response
    h5_ok = h5_status.strip() in ("200", "304")

    print(f"\nBackend API: {'OK' if api_ok else 'FAILED'}")
    print(f"H5 Web: {'OK' if h5_ok else 'FAILED'}")

    ssh.close()
    print("\nSSH connection closed.")
    return 0 if (api_ok and h5_ok) else 1

if __name__ == "__main__":
    sys.exit(main())
