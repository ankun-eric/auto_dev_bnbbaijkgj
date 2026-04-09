#!/usr/bin/env python3
"""Deploy health-v2 feature to production server"""
import paramiko
import os
import sys
import time
import tarfile
import tempfile

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

def get_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    return client

def run_cmd(client, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[:3000])
    if err.strip():
        print(f"[STDERR] {err[:2000]}")
    print(f"[EXIT] {exit_code}")
    return out, err, exit_code

def upload_file(local_path, remote_path):
    client = get_client()
    sftp = client.open_sftp()
    size = os.path.getsize(local_path)
    print(f"\nUploading {os.path.basename(local_path)} ({size//1024}KB) -> {remote_path}")
    sftp.put(local_path, remote_path)
    print("Upload complete.")
    sftp.close()
    client.close()

def make_tar(source_dir, arcname, output_path, excludes=None):
    excludes = excludes or []
    def filter_fn(tarinfo):
        for exc in excludes:
            if exc in tarinfo.name:
                return None
        return tarinfo
    print(f"Packing {source_dir} -> {output_path}")
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_dir, arcname=arcname, filter=filter_fn)
    size = os.path.getsize(output_path)
    print(f"Package size: {size//1024}KB")

def main():
    tmp = tempfile.gettempdir()

    print("=" * 60)
    print("STEP 1: Pack and upload code")
    print("=" * 60)

    # Pack backend
    backend_tar = os.path.join(tmp, "backend_health_v2.tar.gz")
    make_tar(
        os.path.join(LOCAL_DIR, "backend"),
        "backend",
        backend_tar,
        excludes=["__pycache__", ".pyc", ".pyo"]
    )

    # Pack h5-web
    h5_tar = os.path.join(tmp, "h5_health_v2.tar.gz")
    make_tar(
        os.path.join(LOCAL_DIR, "h5-web"),
        "h5-web",
        h5_tar,
        excludes=["node_modules", ".next", ".git"]
    )

    # Pack admin-web
    admin_tar = os.path.join(tmp, "admin_health_v2.tar.gz")
    make_tar(
        os.path.join(LOCAL_DIR, "admin-web"),
        "admin-web",
        admin_tar,
        excludes=["node_modules", ".next", ".git"]
    )

    # Upload all
    upload_file(backend_tar, f"{REMOTE_DIR}/backend_health_v2.tar.gz")
    upload_file(h5_tar, f"{REMOTE_DIR}/h5_health_v2.tar.gz")
    upload_file(admin_tar, f"{REMOTE_DIR}/admin_health_v2.tar.gz")

    print("\n" + "=" * 60)
    print("STEP 2: Extract code on server")
    print("=" * 60)

    client = get_client()
    run_cmd(client, f"cd {REMOTE_DIR} && tar xzf backend_health_v2.tar.gz && rm backend_health_v2.tar.gz")
    run_cmd(client, f"cd {REMOTE_DIR} && tar xzf h5_health_v2.tar.gz && rm h5_health_v2.tar.gz")
    run_cmd(client, f"cd {REMOTE_DIR} && tar xzf admin_health_v2.tar.gz && rm admin_health_v2.tar.gz")
    client.close()

    print("\n" + "=" * 60)
    print("STEP 3: Rebuild containers")
    print("=" * 60)

    client = get_client()
    run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -20", timeout=600)
    client.close()

    client = get_client()
    run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -20", timeout=600)
    client.close()

    client = get_client()
    run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1 | tail -20", timeout=600)
    client.close()

    print("\n" + "=" * 60)
    print("STEP 4: Start containers")
    print("=" * 60)

    client = get_client()
    run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)
    client.close()

    print("\nWaiting 30s for containers to start...")
    time.sleep(30)

    print("\n" + "=" * 60)
    print("STEP 5: Check container status")
    print("=" * 60)

    client = get_client()
    run_cmd(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")

    print("\n" + "=" * 60)
    print("STEP 6: Verify endpoints")
    print("=" * 60)

    BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    endpoints = [
        f"{BASE}/api/health",
        f"{BASE}/api/relation-types",
        f"{BASE}/api/disease-presets?category=chronic",
        f"{BASE}/admin/",
        f"{BASE}/",
    ]
    for ep in endpoints:
        run_cmd(client, f"curl -sk -o /dev/null -w '%{{http_code}} {ep}' '{ep}'", timeout=30)

    client.close()
    print("\n=== Deployment complete ===")

if __name__ == "__main__":
    main()
