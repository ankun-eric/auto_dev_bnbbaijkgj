import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    (f"cd {REMOTE_DIR} && docker compose build --no-cache backend", 600),
    (f"cd {REMOTE_DIR} && docker compose up -d backend", 60),
]
for cmd, timeout in cmds:
    print(f"\n>>> {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out[:3000])
    if err.strip(): print(f"[STDERR] {err[:3000]}")
    print(f"[EXIT] {code}")

print("\nWaiting 20s for backend to start...")
time.sleep(20)

_, stdout, _ = client.exec_command(
    f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health",
    timeout=30
)
print(f"Health check: {stdout.read().decode().strip()}")
client.close()
print("Rebuild complete!")
