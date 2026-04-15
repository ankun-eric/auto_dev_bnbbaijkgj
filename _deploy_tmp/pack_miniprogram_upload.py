#!/usr/bin/env python3
"""Pack miniprogram to zip, upload via SFTP, configure nginx alias for root-level zip URL, verify with requests."""
import datetime
import os
import random
import zipfile

import paramiko
import requests

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USERNAME = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
REMOTE_STATIC = f"{REMOTE_BASE}/static"
# Live nginx include used by gateway container (bind-mounted conf.d)
GATEWAY_CONF_D = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINIPROGRAM_DIR = os.path.join(PROJECT_ROOT, "miniprogram")
OUT_DIR = os.path.join(PROJECT_ROOT, "_deploy_tmp")

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".vscode", ".idea"}
EXCLUDE_EXTS = {".pyc", ".pyo"}


def generate_zip_name():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "%04x" % random.randint(0, 0xFFFF)
    return f"miniprogram_{ts}_{suffix}.zip"


def create_zip(source_dir: str, zip_path: str) -> None:
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if any(f.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                full_path = os.path.join(root, f)
                arcname = os.path.relpath(full_path, os.path.dirname(source_dir))
                zf.write(full_path, arcname)
                count += 1
    print(f"Packed {count} files -> {zip_path} ({os.path.getsize(zip_path) / 1024:.1f} KB)")


def ssh_exec(client: paramiko.SSHClient, cmd: str) -> tuple:
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return out, err


def append_remote_text(client: paramiko.SSHClient, remote_path: str, text: str) -> None:
    stdin, stdout, stderr = client.exec_command(f"cat >> {remote_path}")
    stdin.write(text.encode("utf-8"))
    stdin.channel.shutdown_write()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    stdout.read()
    if err:
        print("append stderr:", err)


# Inside gateway container, project static/ is mounted at /data/static (see docker inspect Mounts)
NGINX_ZIP_BLOCK = f"""
# miniprogram zip at project URL root (files stored under static/ on host)
location ~ ^/autodev/{DEPLOY_ID}/(miniprogram_.+\\.zip)$ {{
    alias /data/static/$1;
    default_type application/zip;
    add_header Content-Disposition "attachment";
    expires 30d;
}}
"""


def ensure_nginx_zip_location(client: paramiko.SSHClient) -> None:
    out, _ = ssh_exec(
        client, f"grep -E 'miniprogram_.+\\\\.zip' {GATEWAY_CONF_D} 2>/dev/null || true"
    )
    if "miniprogram_" in out and ".zip" in out:
        print("Nginx miniprogram zip location already present in gateway conf.d")
        return
    print(f"Appending miniprogram zip location to {GATEWAY_CONF_D} ...")
    append_remote_text(client, GATEWAY_CONF_D, NGINX_ZIP_BLOCK)

    out_docker, _ = ssh_exec(client, "docker ps --format '{{.Names}}' | grep gateway | head -1")
    name = out_docker.strip().split("\n")[0].strip()
    if not name:
        print("Warning: gateway container not found; reload nginx manually")
        return
    o, e = ssh_exec(client, f"docker exec {name} nginx -t 2>&1")
    print("nginx -t:", o, e)
    o2, e2 = ssh_exec(client, f"docker exec {name} nginx -s reload 2>&1")
    print("reload:", o2, e2)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    zip_name = generate_zip_name()
    local_zip = os.path.join(OUT_DIR, zip_name)

    print("Step 1: create zip")
    create_zip(MINIPROGRAM_DIR, local_zip)

    print("Step 2: SFTP upload")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USERNAME, password=PASSWORD, timeout=60)
    ssh_exec(client, f"mkdir -p {REMOTE_STATIC}")

    remote_path = f"{REMOTE_STATIC}/{zip_name}"
    sftp = client.open_sftp()
    sftp.put(local_zip, remote_path)
    st = sftp.stat(remote_path)
    sftp.close()
    print(f"Uploaded {remote_path} ({st.st_size} bytes)")

    print("Step 3: ensure nginx serves .../miniprogram_*.zip from static/")
    ensure_nginx_zip_location(client)
    client.close()

    download_url = f"{BASE_URL}/{zip_name}"
    print("Step 4: HTTP verify", download_url)
    r = requests.get(download_url, timeout=30, allow_redirects=True)
    print("HTTP status:", r.status_code, "Content-Type:", r.headers.get("Content-Type"))

    print("\n--- RESULT ---")
    print("zip filename:", zip_name)
    print("download URL:", download_url)
    print("verify HTTP:", r.status_code)

    if r.status_code != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
