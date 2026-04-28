import paramiko
import os
import sys
import tarfile
import time
import io

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

DIRS_TO_SYNC = ["h5-web", "backend", "admin-web"]
FILES_TO_SYNC = ["docker-compose.prod.yml", ".env"]

EXCLUDE_PATTERNS = [
    "node_modules", ".next", "__pycache__", ".git", "venv", ".venv",
    "build", "dist", ".dart_tool", ".flutter-plugins",
    ".flutter-plugins-dependencies", ".pytest_cache",
]

def should_exclude(path):
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE_PATTERNS:
            return True
        if part.endswith(".pyc"):
            return True
    return False

def create_tar():
    print("[1/4] Creating tar archive of project files...")
    tar_path = os.path.join(LOCAL_DIR, "_deploy_upload.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for d in DIRS_TO_SYNC:
            dir_path = os.path.join(LOCAL_DIR, d)
            if not os.path.isdir(dir_path):
                print(f"  WARNING: Directory {d} not found, skipping")
                continue
            for root, dirs, files in os.walk(dir_path):
                rel_root = os.path.relpath(root, LOCAL_DIR)
                if should_exclude(rel_root):
                    dirs.clear()
                    continue
                dirs[:] = [dd for dd in dirs if dd not in EXCLUDE_PATTERNS]
                for f in files:
                    if f.endswith(".pyc"):
                        continue
                    full_path = os.path.join(root, f)
                    arcname = os.path.relpath(full_path, LOCAL_DIR)
                    tar.add(full_path, arcname=arcname)
            print(f"  Added directory: {d}")

        for f in FILES_TO_SYNC:
            fp = os.path.join(LOCAL_DIR, f)
            if os.path.isfile(fp):
                tar.add(fp, arcname=f)
                print(f"  Added file: {f}")

    size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"  Archive created: {size_mb:.1f} MB")
    return tar_path

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh

def upload_tar(tar_path):
    print("[2/4] Uploading archive to server...")
    ssh = get_ssh()
    sftp = ssh.open_sftp()
    remote_tar = f"{REMOTE_DIR}/_deploy_upload.tar.gz"

    ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
    time.sleep(1)

    size = os.path.getsize(tar_path)
    uploaded = [0]
    last_print = [0]

    def progress(transferred, total):
        uploaded[0] = transferred
        pct = transferred * 100 // total
        if pct - last_print[0] >= 10:
            last_print[0] = pct
            print(f"  Upload progress: {pct}% ({transferred // (1024*1024)}MB / {total // (1024*1024)}MB)")

    sftp.put(tar_path, remote_tar, callback=progress)
    print(f"  Upload complete!")
    sftp.close()
    ssh.close()

def extract_and_build():
    print("[3/4] Extracting archive and rebuilding h5-web container...")
    ssh = get_ssh()
    transport = ssh.get_transport()
    transport.set_keepalive(30)

    cmds = [
        f"cd {REMOTE_DIR} && tar xzf _deploy_upload.tar.gz && rm _deploy_upload.tar.gz && echo 'EXTRACT_OK'",
    ]

    for cmd in cmds:
        print(f"  Running: {cmd[:80]}...")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        out = stdout.read().decode()
        err = stderr.read().decode()
        print(f"  stdout: {out.strip()}")
        if err.strip():
            print(f"  stderr: {err.strip()}")

    print("  Building h5-web container (this may take several minutes)...")
    build_cmd = (
        f"cd {REMOTE_DIR} && "
        f"docker compose -f docker-compose.prod.yml build h5-web --no-cache 2>&1"
    )
    stdin, stdout, stderr = ssh.exec_command(build_cmd, timeout=600)
    
    channel = stdout.channel
    output_lines = []
    while not channel.exit_status_ready():
        if channel.recv_ready():
            chunk = channel.recv(4096).decode(errors='replace')
            for line in chunk.splitlines():
                output_lines.append(line)
                if len(output_lines) % 5 == 0:
                    print(f"  [build] {line.strip()}")
        time.sleep(0.5)
    remaining = channel.recv(65536).decode(errors='replace')
    for line in remaining.splitlines():
        output_lines.append(line)

    exit_code = channel.recv_exit_status()
    build_output = "\n".join(output_lines)

    if exit_code != 0:
        print(f"  docker compose v2 build failed (exit={exit_code}), trying docker-compose v1...")
        build_cmd_v1 = (
            f"cd {REMOTE_DIR} && "
            f"docker-compose -f docker-compose.prod.yml build h5-web --no-cache 2>&1"
        )
        stdin, stdout, stderr = ssh.exec_command(build_cmd_v1, timeout=600)
        channel = stdout.channel
        output_lines = []
        while not channel.exit_status_ready():
            if channel.recv_ready():
                chunk = channel.recv(4096).decode(errors='replace')
                for line in chunk.splitlines():
                    output_lines.append(line)
                    if len(output_lines) % 5 == 0:
                        print(f"  [build] {line.strip()}")
            time.sleep(0.5)
        remaining = channel.recv(65536).decode(errors='replace')
        for line in remaining.splitlines():
            output_lines.append(line)
        exit_code = channel.recv_exit_status()
        build_output = "\n".join(output_lines)

    if exit_code != 0:
        print(f"  BUILD FAILED (exit={exit_code})")
        print(f"  Last 30 lines of build output:")
        for line in output_lines[-30:]:
            print(f"    {line}")
        ssh.close()
        return False
    
    print(f"  Build succeeded!")

    print("  Starting h5-web container...")
    up_cmd = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1"
    stdin, stdout, stderr = ssh.exec_command(up_cmd, timeout=120)
    out = stdout.read().decode()
    err_out = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    print(f"  {out.strip()}")
    if err_out.strip():
        print(f"  {err_out.strip()}")

    if exit_code != 0:
        up_cmd_v1 = f"cd {REMOTE_DIR} && docker-compose -f docker-compose.prod.yml up -d h5-web 2>&1"
        stdin, stdout, stderr = ssh.exec_command(up_cmd_v1, timeout=120)
        out = stdout.read().decode()
        print(f"  {out.strip()}")

    print("  Checking container status...")
    stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1", timeout=30)
    out = stdout.read().decode()
    print(f"  {out.strip()}")

    ssh.close()
    return True

def verify_deployment():
    print("[4/4] Verifying deployment URLs...")
    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    urls = [
        ("H5 Frontend", "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/"),
        ("Admin Panel", "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/"),
        ("API Base", "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/"),
        ("Products Categories API", "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/products/categories"),
    ]

    time.sleep(5)

    results = []
    for name, url in urls:
        try:
            req = urllib.request.Request(url, method='GET')
            req.add_header('User-Agent', 'Mozilla/5.0 DeployCheck')
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            code = resp.getcode()
            results.append((name, url, code, "OK"))
            print(f"  {name}: {code} OK")
        except urllib.error.HTTPError as e:
            results.append((name, url, e.code, "HTTP Error"))
            status = "OK" if e.code in (200, 301, 302, 304, 307, 308) else "FAIL"
            print(f"  {name}: {e.code} {status}")
        except Exception as e:
            results.append((name, url, 0, str(e)))
            print(f"  {name}: FAILED - {e}")

    return results

if __name__ == "__main__":
    try:
        tar_path = create_tar()
        upload_tar(tar_path)
        os.remove(tar_path)
        success = extract_and_build()
        if success:
            results = verify_deployment()
            print("\n=== DEPLOYMENT COMPLETE ===")
            for name, url, code, status in results:
                print(f"  {name}: {code} {status}")
        else:
            print("\n=== DEPLOYMENT FAILED - Build error ===")
            sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
