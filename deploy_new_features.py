"""
Deploy new features to remote server via SSH/SFTP.
Packages backend, h5-web, admin-web and rebuilds containers.
"""
import paramiko
import os
import tarfile
import time
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDES = {
    "__pycache__", ".pytest_cache", ".git", "node_modules",
    ".next", "dist", "build", ".turbo", "*.pyc", ".env.local",
    "venv", ".venv", "*.egg-info", ".mypy_cache",
}


def should_exclude(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDES:
            return True
    if path.endswith(".pyc"):
        return True
    return False


def create_tar(local_path: str, tar_path: str, arcname: str):
    """Create a .tar.gz archive of a directory."""
    with tarfile.open(tar_path, "w:gz") as tar:
        for root, dirs, files in os.walk(local_path):
            # Filter out excluded dirs
            dirs[:] = [d for d in dirs if d not in EXCLUDES]
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, os.path.dirname(local_path))
                rel_path = rel_path.replace("\\", "/")
                if not should_exclude(rel_path):
                    tar.add(full_path, arcname=f"{arcname}/{os.path.relpath(full_path, local_path).replace(chr(92), '/')}")
    size = os.path.getsize(tar_path) / 1024 / 1024
    print(f"  Created {tar_path} ({size:.1f} MB)")


def run_ssh_command(client: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    """Run a command via SSH and return (exit_code, stdout, stderr)."""
    print(f"\n[SSH] {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"  STDOUT: {out.strip()[:500]}")
    if err.strip() and code != 0:
        print(f"  STDERR: {err.strip()[:500]}")
    print(f"  Exit code: {code}")
    return code, out, err


def upload_file(sftp: paramiko.SFTPClient, local_path: str, remote_path: str):
    """Upload a single file via SFTP with progress."""
    size = os.path.getsize(local_path) / 1024 / 1024
    print(f"  Uploading {os.path.basename(local_path)} ({size:.1f} MB) -> {remote_path}")
    sftp.put(local_path, remote_path)
    print(f"  Upload complete.")


def main():
    print("=" * 60)
    print("bini-health Deployment Script")
    print(f"Target: {HOST}:{PORT}")
    print(f"DEPLOY_ID: {DEPLOY_ID}")
    print("=" * 60)

    # Connect SSH
    print("\n[1] Connecting to server...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("  Connected!")

    sftp = client.open_sftp()

    # Check container status
    print("\n[2] Checking current container status...")
    code, out, err = run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps --format 'table {{{{.Name}}}}\t{{{{.Status}}}}'",
        timeout=30
    )

    # Create temp directory
    tmp_dir = os.path.join(LOCAL_DIR, "_deploy_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    # === Package and upload backend ===
    print("\n[3] Packaging backend...")
    backend_tar = os.path.join(tmp_dir, "backend.tar.gz")
    create_tar(os.path.join(LOCAL_DIR, "backend"), backend_tar, "backend")

    print("\n[4] Uploading backend archive...")
    upload_file(sftp, backend_tar, f"{REMOTE_DIR}/backend.tar.gz")

    print("\n[5] Extracting backend on server...")
    code, out, err = run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && rm -rf backend_new && tar -xzf backend.tar.gz && "
        f"rm -rf backend_old && (mv backend backend_old 2>/dev/null || true) && "
        f"mv backend backend_new && rm -rf backend && mv backend_new backend && "
        f"rm -f backend.tar.gz && echo 'Backend extracted OK'",
        timeout=60
    )
    if code != 0:
        # Simpler approach
        run_ssh_command(
            client,
            f"cd {REMOTE_DIR} && tar -xzf backend.tar.gz --overwrite && rm -f backend.tar.gz && echo 'Done'",
            timeout=60
        )

    # === Package and upload h5-web ===
    print("\n[6] Packaging h5-web...")
    h5_tar = os.path.join(tmp_dir, "h5-web.tar.gz")
    create_tar(os.path.join(LOCAL_DIR, "h5-web"), h5_tar, "h5-web")

    print("\n[7] Uploading h5-web archive...")
    upload_file(sftp, h5_tar, f"{REMOTE_DIR}/h5-web.tar.gz")

    print("\n[8] Extracting h5-web on server...")
    run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && tar -xzf h5-web.tar.gz --overwrite && rm -f h5-web.tar.gz && echo 'h5-web extracted OK'",
        timeout=60
    )

    # === Package and upload admin-web ===
    print("\n[9] Packaging admin-web...")
    admin_tar = os.path.join(tmp_dir, "admin-web.tar.gz")
    create_tar(os.path.join(LOCAL_DIR, "admin-web"), admin_tar, "admin-web")

    print("\n[10] Uploading admin-web archive...")
    upload_file(sftp, admin_tar, f"{REMOTE_DIR}/admin-web.tar.gz")

    print("\n[11] Extracting admin-web on server...")
    run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && tar -xzf admin-web.tar.gz --overwrite && rm -f admin-web.tar.gz && echo 'admin-web extracted OK'",
        timeout=60
    )

    # === Rebuild backend container ===
    print("\n[12] Building and restarting backend container...")
    code, out, err = run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -20",
        timeout=600
    )
    if code != 0:
        print(f"  WARNING: Backend build failed, checking logs...")
        run_ssh_command(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml logs backend --tail=50", timeout=30)

    run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend",
        timeout=120
    )

    # === Rebuild h5-web container ===
    print("\n[13] Building and restarting h5-web container...")
    code, out, err = run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -20",
        timeout=600
    )
    if code != 0:
        print(f"  WARNING: h5-web build failed")

    run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web",
        timeout=120
    )

    # === Rebuild admin-web container ===
    print("\n[14] Building and restarting admin-web container...")
    code, out, err = run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -20",
        timeout=600
    )
    if code != 0:
        print(f"  WARNING: admin-web build failed")

    run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web",
        timeout=120
    )

    # === Wait and check ===
    print("\n[15] Waiting 30s for containers to start...")
    time.sleep(30)

    print("\n[16] Checking final container status...")
    run_ssh_command(
        client,
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps",
        timeout=30
    )

    run_ssh_command(
        client,
        f"docker ps --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}' | grep {DEPLOY_ID}",
        timeout=30
    )

    sftp.close()
    client.close()
    print("\n[DONE] Deployment script completed!")


if __name__ == "__main__":
    main()
