"""One-off: zip miniprogram, inspect gateway nginx, upload via SFTP, print download URL."""
import os
import random
import re
import sys
import zipfile
from datetime import datetime

import paramiko

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
MINIPROGRAM = os.path.join(PROJECT_ROOT, "miniprogram")
BASE_URL_PATH = "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
HOST = "43.135.169.167"
USER = "ubuntu"
PASSWORD = "Newbang888"

EXCLUDE_DIR_NAMES = {".git", "node_modules", "__pycache__", ".idea", ".vscode"}
EXCLUDE_FILE_NAMES = {".DS_Store"}


def should_skip(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIR_NAMES:
            return True
        if p.startswith(".") and p not in {".", ".."} and p in EXCLUDE_FILE_NAMES:
            pass
    base = os.path.basename(rel_path)
    if base in EXCLUDE_FILE_NAMES:
        return True
    return False


def make_zip(dest_zip: str) -> None:
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MINIPROGRAM):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES and not d.startswith(".git")]
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, MINIPROGRAM)
                if should_skip(rel):
                    continue
                zf.write(full, arcname=os.path.join("miniprogram", rel).replace("\\", "/"))


def ssh_exec(client: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main() -> int:
    now = datetime.now()
    suffix = f"{random.randint(0, 0xFFFF):04x}"
    name = f"miniprogram_{now:%Y%m%d}_{now:%H%M%S}_{suffix}.zip"
    dest_zip = os.path.join(PROJECT_ROOT, name)
    print(f"Creating {dest_zip} ...")
    make_zip(dest_zip)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    # Find gateway nginx conf mentioning this autodev path
    find_cmd = (
        "sudo grep -r '3b7b999d-e51c-4c0d-8f6e-baf90cd26857' "
        "/etc/nginx 2>/dev/null; "
        "sudo grep -r '3b7b999d' /etc/nginx/conf.d 2>/dev/null; "
        "ls -la /etc/nginx/conf.d 2>/dev/null | head -50"
    )
    code, out, err = ssh_exec(client, find_cmd)
    print("=== grep autodev in nginx ===")
    print(out or err)

    # Common locations for gateway
    probe = (
        "for d in /etc/nginx/conf.d /etc/nginx/sites-enabled /home/ubuntu/gateway-nginx/conf.d; do "
        "[ -d \"$d\" ] && echo DIR:$d && sudo ls -la \"$d\" 2>/dev/null; done; "
        "docker ps --format '{{.Names}}' 2>/dev/null | head -30"
    )
    _, out2, _ = ssh_exec(client, probe)
    print("=== dirs + docker ===")
    print(out2)

    # Try to read conf files that mention autodev or proxy_pass to project
    read_conf = (
        "sudo sh -c 'grep -l autodev /etc/nginx/conf.d/*.conf 2>/dev/null | head -5 | xargs -r cat'"
    )
    _, out3, _ = ssh_exec(client, read_conf)
    print("=== conf snippets ===")
    print(out3[:8000] if out3 else "(empty)")

    sftp = client.open_sftp()

    # Candidate remote dirs: try common static roots
    candidates = [
        "/home/ubuntu/autodev-3b7b999d-e51c-4c0d-8f6e-baf90cd26857",
        "/home/ubuntu/bnbbaijkgj",
        "/var/www/autodev-3b7b999d-e51c-4c0d-8f6e-baf90cd26857",
    ]
    remote_dir = None
    for c in candidates:
        try:
            sftp.stat(c)
            remote_dir = c
            print(f"Found remote dir: {c}")
            break
        except OSError:
            continue

    if not remote_dir:
        # List home
        _, home_list, _ = ssh_exec(client, "ls -la /home/ubuntu")
        print("=== /home/ubuntu ===")
        print(home_list)
        for line in home_list.splitlines():
            if "3b7b" in line or "autodev" in line.lower() or "bnbb" in line.lower():
                parts = line.split()
                if len(parts) >= 9:
                    remote_dir = "/home/ubuntu/" + parts[-1]
                    break

    if not remote_dir:
        remote_dir = "/home/ubuntu"
        print(f"Fallback upload dir: {remote_dir}")

    remote_path = f"{remote_dir.rstrip('/')}/{name}"
    print(f"Uploading to {remote_path} ...")
    sftp.put(dest_zip, remote_path)
    sftp.close()

    # If nginx proxies to a container volume, we may need to copy into container
    _, vol_check, _ = ssh_exec(
        client,
        "docker ps -a --format '{{.Names}}' | grep -iE 'h5|admin|frontend|nginx|3b7b|autodev' || true",
    )
    print("=== docker names match ===")
    print(vol_check)

    client.close()

    base = f"https://newbb.bangbangvip.com{BASE_URL_PATH}/{name}"
    print(f"DOWNLOAD_URL={base}")
    print(f"ZIP_NAME={name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
