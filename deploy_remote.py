import paramiko
import sys
import os
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

def get_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    return client

def run_cmd(client, cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[STDERR] {err}")
    print(f"[EXIT CODE] {exit_code}")
    return out, err, exit_code

def upload_file(local_path, remote_path):
    client = get_client()
    sftp = client.open_sftp()
    print(f"\nUploading {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)
    print("Upload complete.")
    sftp.close()
    client.close()

def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    if step in ("upload", "all"):
        local_file = os.path.join(os.path.dirname(__file__), "backend_update.tar.gz")
        remote_file = f"{REMOTE_DIR}/backend_update.tar.gz"
        upload_file(local_file, remote_file)

    if step in ("deploy", "all"):
        client = get_client()
        run_cmd(client, f"cd {REMOTE_DIR} && tar xzf backend_update.tar.gz")
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend", timeout=300)
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d backend")
        print("\nWaiting 15s for backend to start...")
        time.sleep(15)
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml ps")
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml logs --tail=30 backend")
        client.close()

    if step in ("health", "all"):
        client = get_client()
        run_cmd(client, f"curl -s https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health")
        client.close()

if __name__ == "__main__":
    main()
