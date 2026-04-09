import paramiko
import scp as scp_module
import sys
import time
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
REMOTE_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
LOCAL_ADMIN_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin-web")

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh

def run_cmd(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT CODE] {exit_code}")
    return out, err, exit_code

def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    ssh = get_ssh()

    if step in ("check", "all"):
        print("=" * 60)
        print("STEP 1: Check current container status")
        print("=" * 60)
        run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps")

    if step in ("transfer", "all"):
        print("\n" + "=" * 60)
        print("STEP 2: Transfer admin-web source to server")
        print("=" * 60)
        run_cmd(ssh, f"rm -rf {REMOTE_DIR}/admin-web.bak && mv {REMOTE_DIR}/admin-web {REMOTE_DIR}/admin-web.bak || true")
        
        # Use tar + SFTP to transfer, excluding node_modules and .next
        import subprocess, tempfile
        tar_path = os.path.join(tempfile.gettempdir(), "admin-web-deploy.tar.gz")
        print("Creating tar archive (excluding node_modules, .next)...")
        subprocess.run([
            "tar", "-czf", tar_path,
            "--exclude=node_modules", "--exclude=.next",
            "-C", os.path.dirname(LOCAL_ADMIN_WEB),
            "admin-web"
        ], check=True)
        tar_size_mb = os.path.getsize(tar_path) / (1024 * 1024)
        print(f"Archive size: {tar_size_mb:.1f} MB")
        
        sftp = ssh.open_sftp()
        remote_tar = f"{REMOTE_DIR}/admin-web-deploy.tar.gz"
        print(f"Uploading to {remote_tar} ...")
        sftp.put(tar_path, remote_tar)
        sftp.close()
        print("Upload complete.")
        os.remove(tar_path)
        
        print("Extracting on server...")
        run_cmd(ssh, f"cd {REMOTE_DIR} && tar -xzf admin-web-deploy.tar.gz && rm -f admin-web-deploy.tar.gz")
        run_cmd(ssh, f"ls -la {REMOTE_DIR}/admin-web/")

    if step in ("build", "all"):
        print("\n" + "=" * 60)
        print("STEP 3: Rebuild admin-web container (no-cache)")
        print("=" * 60)
        out, err, code = run_cmd(ssh, 
            f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1",
            timeout=600)
        if code != 0:
            print("ERROR: Build failed!")
            ssh.close()
            sys.exit(1)

        print("\nRestarting admin-web container...")
        run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1")

    if step in ("verify", "all"):
        print("\n" + "=" * 60)
        print("STEP 4: Wait for container and verify")
        print("=" * 60)
        print("Waiting 15 seconds for container startup...")
        time.sleep(15)

        run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps")
        
        out, err, code = run_cmd(ssh, f"docker logs --tail 30 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-admin 2>&1")
        
        print("\nVerifying admin page accessibility...")
        out, err, code = run_cmd(ssh, 
            "curl -s -o /dev/null -w '%{http_code}' -L --max-time 15 https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/")
        http_code = out.strip()
        print(f"HTTP Status Code: {http_code}")
        
        if http_code in ("200", "304"):
            print("\n✅ Admin page is accessible! Deployment successful!")
        else:
            print(f"\n⚠️ Admin page returned HTTP {http_code}, checking further...")
            run_cmd(ssh, 
                "curl -s -L --max-time 15 https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/ | head -50")

    ssh.close()
    print("\n" + "=" * 60)
    print("Deployment script finished.")
    print("=" * 60)

if __name__ == "__main__":
    main()
