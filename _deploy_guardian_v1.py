"""Deploy guardian relationship & page optimization to server."""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def ssh_exec(client, cmd, timeout=300):
    print(f"  > {cmd[:120]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-2000:] if len(out) > 2000 else out)
    if err.strip() and rc != 0:
        print(f"  STDERR: {err[-1000:]}")
    return rc, out, err

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    print("Connected to server.")

    # Step 1: Git pull latest code
    print("\n=== Step 1: Git pull ===")
    rc, out, err = ssh_exec(client, f"cd {PROJECT_DIR} && git stash && git pull origin master --no-edit")
    if rc != 0 and "Already up to date" not in out:
        print(f"Git pull failed (rc={rc}), trying force reset...")
        ssh_exec(client, f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master")

    # Step 2: Rebuild backend container (no-cache)
    print("\n=== Step 2: Rebuild backend ===")
    rc, out, err = ssh_exec(client, f"cd {PROJECT_DIR} && docker compose build --no-cache backend", timeout=600)
    if rc != 0:
        print("Backend build failed!")
        sys.exit(1)

    # Step 3: Rebuild h5-web container (no-cache)
    print("\n=== Step 3: Rebuild h5-web ===")
    rc, out, err = ssh_exec(client, f"cd {PROJECT_DIR} && docker compose build --no-cache h5-web", timeout=600)
    if rc != 0:
        print("H5-web build failed!")
        sys.exit(1)

    # Step 4: Restart services
    print("\n=== Step 4: Restart services ===")
    rc, out, err = ssh_exec(client, f"cd {PROJECT_DIR} && docker compose up -d --force-recreate backend h5-web", timeout=120)

    # Step 5: Wait for services to start
    print("\n=== Step 5: Waiting for services... ===")
    time.sleep(15)

    # Step 6: Health check
    print("\n=== Step 6: Health checks ===")
    checks = [
        ("Backend API docs", "curl -s -o /dev/null -w '%{http_code}' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs"),
        ("H5 homepage", "curl -s -o /dev/null -w '%{http_code}' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/"),
        ("Reverse guardian API", "curl -s -o /dev/null -w '%{http_code}' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/reverse-guardian/guardian-count"),
        ("Health profile", "curl -s -o /dev/null -w '%{http_code}' -L https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile"),
    ]
    
    all_ok = True
    for name, cmd in checks:
        rc, out, err = ssh_exec(client, cmd)
        status = out.strip()
        ok = status in ("200", "307", "308", "401", "403", "422")
        print(f"  {name}: HTTP {status} {'OK' if ok else 'FAIL'}")
        if not ok:
            all_ok = False

    # Step 7: Docker status
    print("\n=== Step 7: Docker status ===")
    ssh_exec(client, f"docker ps --filter 'name=6b099ed3' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    client.close()
    
    if all_ok:
        print("\n=== DEPLOYMENT SUCCESS ===")
    else:
        print("\n=== DEPLOYMENT COMPLETED WITH WARNINGS ===")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
