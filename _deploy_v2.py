#!/usr/bin/env python3
"""Deploy project to remote server via SSH - efficient version."""
import paramiko
import os
import sys
import time
import tarfile
import io

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_DIR = r"C:\auto_output\bnbbaijkgj"

EXCLUDE_DIRS = {
    "node_modules", ".next", "__pycache__", ".git", ".pytest_cache",
    "dist", "build", ".tools", "apk_download", "build_artifacts",
    "_deploy_tmp", ".chat_attachments", ".chat_output", ".chat_prompts",
    ".consulting_output", "ui_design_outputs", "uploads", "docs", "mem",
    "user_docs", ".cursor", "tests", ".venv", "venv"
}

EXCLUDE_EXTS = {".tar.gz", ".tar", ".zip", ".png", ".exe", ".apk", ".ipa", ".pyc"}

DIRS_TO_SYNC = ["backend", "admin-web", "h5-web", "miniprogram"]
FILES_TO_SYNC = ["docker-compose.prod.yml"]

def should_include(path, arcname):
    parts = arcname.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIRS:
            return False
    _, ext = os.path.splitext(path)
    if ext in EXCLUDE_EXTS:
        return False
    return True

def ssh_exec(client, cmd, timeout=300):
    print(f"  [SSH] {cmd[:150]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        for line in out.strip().split("\n")[:30]:
            print(f"    {line}")
    if err.strip() and code != 0:
        for line in err.strip().split("\n")[:15]:
            print(f"    [ERR] {line}")
    return code, out, err

def create_tar(dirs, files, base_dir):
    buf = io.BytesIO()
    count = 0
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for d in dirs:
            full = os.path.join(base_dir, d)
            if not os.path.isdir(full):
                print(f"  [SKIP] Dir not found: {d}")
                continue
            for root, subdirs, fnames in os.walk(full):
                rel = os.path.relpath(root, base_dir)
                parts = rel.replace("\\", "/").split("/")
                subdirs[:] = [s for s in subdirs if s not in EXCLUDE_DIRS]
                for fn in fnames:
                    fpath = os.path.join(root, fn)
                    arcname = os.path.join(rel, fn).replace("\\", "/")
                    if should_include(fpath, arcname):
                        try:
                            tar.add(fpath, arcname=arcname)
                            count += 1
                        except Exception:
                            pass
            print(f"  Added dir: {d}")
        for f in files:
            full = os.path.join(base_dir, f)
            if os.path.isfile(full):
                tar.add(full, arcname=f)
                count += 1
                print(f"  Added file: {f}")
    buf.seek(0)
    print(f"  Total files: {count}")
    return buf

def main():
    print("=== Step 1: Creating archive (excluding node_modules etc.) ===")
    tar_buf = create_tar(DIRS_TO_SYNC, FILES_TO_SYNC, PROJECT_DIR)
    tar_size = tar_buf.getbuffer().nbytes
    print(f"  Archive size: {tar_size / 1024 / 1024:.1f} MB")

    print("\n=== Step 2: Connecting to server ===")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    print("  Connected!")

    print("\n=== Step 3: Uploading archive ===")
    sftp = client.open_sftp()
    ssh_exec(client, f"mkdir -p {REMOTE_DIR}")
    remote_tar = f"{REMOTE_DIR}/deploy_package.tar.gz"
    sftp.putfo(tar_buf, remote_tar)
    print(f"  Uploaded to {remote_tar}")

    print("\n=== Step 4: Extracting archive ===")
    ssh_exec(client, f"cd {REMOTE_DIR} && tar xzf deploy_package.tar.gz")

    print("\n=== Step 5: Building containers ===")
    code, out, err = ssh_exec(client, 
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build 2>&1 | tail -30", 
        timeout=600)
    if code != 0:
        print("  Build failed, retrying with --no-cache for failed services...")
        code, out, err = ssh_exec(client, 
            f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1 | tail -50",
            timeout=600)
        if code != 0:
            print(f"  Build failed again. Error: {err[:500]}")

    print("\n=== Step 6: Starting containers ===")
    ssh_exec(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down 2>&1", timeout=120)
    time.sleep(3)
    code, out, err = ssh_exec(client, 
        f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1",
        timeout=120)

    print("\n=== Step 7: Waiting for services (20s) ===")
    time.sleep(20)
    ssh_exec(client, f"docker ps --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    print("\n=== Step 8: Checking container logs for errors ===")
    ssh_exec(client, f"docker logs {DEPLOY_ID}-backend 2>&1 | tail -20")

    print("\n=== Step 9: Verifying access ===")
    base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    urls = [
        (f"{base}/api/docs", "API Docs"),
        (f"{base}/admin/", "Admin Web"),
        (f"{base}/", "H5 Web"),
    ]
    all_ok = True
    for url, name in urls:
        code, out, err = ssh_exec(client, f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'")
        status = out.strip().replace("'", "")
        ok = status in ("200", "301", "302", "304")
        print(f"  {name}: {url} => {status} {'OK' if ok else 'FAIL'}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n=== ALL SERVICES ACCESSIBLE! Deployment successful! ===")
    else:
        print("\n=== Some services not accessible. Checking gateway... ===")
        ssh_exec(client, "docker exec gateway-nginx nginx -t 2>&1")
        ssh_exec(client, f"docker exec gateway-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -A5 '{DEPLOY_ID}'")

    sftp.close()
    client.close()
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
