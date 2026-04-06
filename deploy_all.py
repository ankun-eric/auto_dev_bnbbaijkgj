import paramiko
import os
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

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
        print(out[:2000])
    if err.strip():
        print(f"[STDERR] {err[:2000]}")
    print(f"[EXIT] {exit_code}")
    return out, err, exit_code

def upload_file(local_path, remote_path):
    client = get_client()
    sftp = client.open_sftp()
    print(f"\nUploading {os.path.basename(local_path)} -> {remote_path}")
    sftp.put(local_path, remote_path)
    print("Upload complete.")
    sftp.close()
    client.close()

def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    if step in ("upload", "all"):
        pkg = os.path.join(LOCAL_DIR, "deploy_package.tar.gz")
        if not os.path.exists(pkg):
            print(f"ERROR: {pkg} not found")
            return
        upload_file(pkg, f"{REMOTE_DIR}/deploy_package.tar.gz")

    if step in ("extract", "all"):
        client = get_client()
        run_cmd(client, f"cd {REMOTE_DIR} && tar xzf deploy_package.tar.gz")
        run_cmd(client, f"cp {REMOTE_DIR}/docker-compose.prod.yml {REMOTE_DIR}/docker-compose.yml")
        client.close()

    if step in ("build", "all"):
        client = get_client()
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose down --timeout 30", timeout=120)
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose build --no-cache backend", timeout=600)
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose build --no-cache admin-web", timeout=600)
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose build --no-cache h5-web", timeout=600)
        client.close()

    if step in ("up", "all"):
        client = get_client()
        run_cmd(client, f"cd {REMOTE_DIR} && docker compose up -d", timeout=120)
        print("\nWaiting 30s for containers to start...")
        time.sleep(30)
        run_cmd(client, f"docker ps --filter name={DEPLOY_ID}")
        client.close()

    if step in ("gateway", "all"):
        client = get_client()
        run_cmd(client, f"cp {REMOTE_DIR}/gateway-routes.conf /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf")
        run_cmd(client, "docker exec gateway-nginx nginx -t")
        run_cmd(client, "docker exec gateway-nginx nginx -s reload")
        client.close()

    if step in ("verify", "all"):
        client = get_client()
        run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health")
        run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/")
        run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/")
        client.close()

    print("\n=== Deployment complete ===")

if __name__ == "__main__":
    main()
