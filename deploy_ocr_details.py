"""Deploy OCR details feature to remote server."""
import os
import sys
import time
import subprocess
import paramiko
import tarfile
import io

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return client

def run_remote(client, cmd, timeout=300):
    print(f"  >> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  [OUT] {out.strip()[:500]}")
    if err.strip():
        print(f"  [ERR] {err.strip()[:500]}")
    return code, out, err

def upload_dir(client, local_dir, remote_dir, excludes=None):
    """Upload a local directory to remote using tar over SFTP."""
    excludes = excludes or []
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(local_dir):
            dirs[:] = [d for d in dirs if d not in excludes]
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, local_dir)
                if any(ex in arcname for ex in excludes):
                    continue
                tar.add(fp, arcname=arcname)
    buf.seek(0)
    data = buf.read()

    sftp = client.open_sftp()
    tmp = f"/tmp/upload_{DEPLOY_ID}_{int(time.time())}.tar.gz"
    with sftp.open(tmp, "wb") as rf:
        rf.write(data)

    run_remote(client, f"mkdir -p {remote_dir}")
    run_remote(client, f"cd {remote_dir} && tar xzf {tmp} --overwrite")
    run_remote(client, f"rm -f {tmp}")
    sftp.close()
    print(f"  Uploaded {local_dir} -> {remote_dir} ({len(data)} bytes)")

def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    print("=" * 60)
    print("Deploying OCR Details Feature")
    print("=" * 60)

    client = ssh_connect()
    print("[1/5] Connected to server")

    # Upload backend
    print("[2/5] Uploading backend...")
    backend_dir = os.path.join(project_root, "backend")
    upload_dir(client, backend_dir, f"{REMOTE_DIR}/backend",
               excludes=["__pycache__", ".pytest_cache", "tests", ".git", "node_modules", ".venv"])

    # Upload admin-web
    print("[3/5] Uploading admin-web...")
    admin_dir = os.path.join(project_root, "admin-web")
    upload_dir(client, admin_dir, f"{REMOTE_DIR}/admin-web",
               excludes=["node_modules", ".next", ".git", "__pycache__"])

    # Upload docker-compose
    sftp = client.open_sftp()
    dc_local = os.path.join(project_root, "docker-compose.prod.yml")
    sftp.put(dc_local, f"{REMOTE_DIR}/docker-compose.prod.yml")
    sftp.close()
    print("  Uploaded docker-compose.prod.yml")

    # Rebuild containers
    print("[4/5] Rebuilding backend and admin-web containers...")
    code, out, err = run_remote(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend admin-web",
        timeout=600,
    )
    if code != 0:
        print(f"  Build failed with code {code}")

    print("[5/5] Restarting containers...")
    run_remote(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend admin-web", timeout=120)

    # Wait for containers
    time.sleep(10)
    run_remote(client, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'")

    # Verify health
    code, out, err = run_remote(client, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000/api/health")
    print(f"  Backend health: HTTP {out.strip()}")

    client.close()
    print("\nDeployment complete!")

if __name__ == "__main__":
    main()
