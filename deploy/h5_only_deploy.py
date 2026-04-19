"""Deploy only the H5 changes (2 files) and rebuild h5 container."""
import paramiko
import os
import sys
import time

SERVER = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_DIR = f'/home/ubuntu/{DEPLOY_ID}'

# (local_relpath, remote_relpath)
FILES = [
    ('h5-web/src/app/drug/page.tsx', 'h5-web/src/app/drug/page.tsx'),
    ('h5-web/src/app/chat/[sessionId]/page.tsx', 'h5-web/src/app/chat/[sessionId]/page.tsx'),
]

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    last_err = None
    for i in range(3):
        try:
            ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
            return ssh
        except Exception as e:
            last_err = e
            print(f"  connect retry {i+1}: {e}")
            time.sleep(3)
    raise last_err

def run(ssh, cmd, timeout=600):
    print(f"$ {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print(f"[stderr] {err}")
    print(f"[exit={code}]")
    return out, err, code

def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("=== Connecting to server ===")
    ssh = connect()
    sftp = ssh.open_sftp()

    print("=== Listing compose files ===")
    run(ssh, f'ls {REMOTE_DIR}/*.yml 2>/dev/null || true')

    print("=== Uploading H5 files ===")
    for local_rel, remote_rel in FILES:
        local_full = os.path.join(project_dir, local_rel.replace('/', os.sep))
        remote_full = f'{REMOTE_DIR}/{remote_rel}'
        if not os.path.exists(local_full):
            print(f"!! local missing: {local_full}")
            continue
        # Ensure remote dir exists
        remote_parent = remote_full.rsplit('/', 1)[0]
        run(ssh, f'mkdir -p "{remote_parent}"')
        size = os.path.getsize(local_full)
        print(f"Uploading {local_rel} -> {remote_full} ({size} bytes)")
        sftp.put(local_full, remote_full)
        print("  OK")

    sftp.close()

    print("=== Inspecting docker-compose project ===")
    run(ssh, f'cd {REMOTE_DIR} && head -n 3 docker-compose.prod.yml && grep -E "^[[:space:]]+[a-z0-9_-]+:" docker-compose.prod.yml | head -n 30')

    print("=== Container status before rebuild ===")
    run(ssh, f'docker ps --format "table {{{{.Names}}}}\\t{{{{.Status}}}}" | grep {DEPLOY_ID} || true')

    print("=== Rebuilding h5 container only ===")
    out, err, code = run(ssh,
        f'cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d --build h5 2>&1',
        timeout=1800)
    if code != 0:
        print("!! h5 build failed")
        ssh.close()
        sys.exit(1)

    print("=== Wait 5s then check status ===")
    time.sleep(5)
    run(ssh, f'docker ps --format "table {{{{.Names}}}}\\t{{{{.Status}}}}" | grep {DEPLOY_ID} || true')

    print("=== H5 container logs (tail 80) ===")
    run(ssh, f'docker logs {DEPLOY_ID}-h5-1 --tail 80 2>&1 || docker logs {DEPLOY_ID}_h5_1 --tail 80 2>&1 || true')

    ssh.close()
    print("=== Done ===")

if __name__ == '__main__':
    main()
