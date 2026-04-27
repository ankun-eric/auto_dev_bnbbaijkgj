import paramiko
import time

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def run_cmd(client, cmd, timeout=120):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out[:3000])
    if err:
        print(f"STDERR: {err[:2000]}")
    print(f"Exit code: {exit_code}")
    return out, err, exit_code

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)

print("=== Restarting containers with docker compose v2 ===")
run_cmd(client, f"cd {REMOTE_DIR} && docker compose up -d backend h5-web", timeout=120)

print("\nWaiting 15 seconds for containers to start...")
time.sleep(15)

run_cmd(client, f"cd {REMOTE_DIR} && docker compose ps")

print("\n=== Checking backend logs ===")
run_cmd(client, f"cd {REMOTE_DIR} && docker compose logs --tail=20 backend")

print("\n=== Verification ===")
base_url = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

urls = [
    (f"{base_url}/api/products/categories", "Categories API"),
    (f"{base_url}/api/products?category_id=recommend", "Products with recommend category"),
    (f"{base_url}/", "H5 Frontend"),
]

for url, label in urls:
    print(f"\n--- {label}: {url}")
    run_cmd(client, f'curl -s -o /tmp/resp.txt -w "HTTP_STATUS:%{{http_code}}" "{url}" && echo "" && head -c 800 /tmp/resp.txt')

client.close()
print("\nDone!")
