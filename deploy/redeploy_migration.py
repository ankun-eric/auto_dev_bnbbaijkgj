import paramiko, time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30,
               look_for_keys=False, allow_agent=False)

def run(cmd, timeout=120):
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    out = b""
    err = b""
    deadline = time.time() + timeout
    while not chan.exit_status_ready():
        if time.time() > deadline:
            break
        if chan.recv_ready():
            out += chan.recv(65536)
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(65536)
        time.sleep(0.1)
    try:
        out += chan.recv(65536)
    except:
        pass
    try:
        err += chan.recv_stderr(65536)
    except:
        pass
    return out.decode(errors='replace'), chan.exit_status

print("=== Step 1: Pull latest code ===")
git_url = f"https://{GIT_USER}:{GIT_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"
out, ec = run(f"cd {PROJECT_DIR} && git fetch --depth=1 {git_url} master 2>&1 && git reset --hard FETCH_HEAD 2>&1", timeout=60)
print(out[:500])

out, ec = run(f"cd {PROJECT_DIR} && git log -1 --oneline")
print(f"Latest commit: {out.strip()}")

print("\n=== Step 2: Rebuild backend ===")
BUILD_COMMIT = out.strip().split()[0] if out.strip() else "unknown"
out, ec = run(f"cd {PROJECT_DIR} && export BUILD_COMMIT='{BUILD_COMMIT}' && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1", timeout=600)
lines = out.strip().split('\n')
for line in lines[-15:]:
    print(f"  {line}")

print("\n=== Step 3: Restart backend ===")
out, ec = run(f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1")
print(out[:500])

print("Waiting for backend healthy...")
for i in range(24):
    time.sleep(5)
    out, _ = run(f"docker inspect {DEPLOY_ID}-backend --format '{{{{.State.Health.Status}}}}'")
    print(f"  [{i+1}/24] {out.strip()}")
    if out.strip() == "healthy":
        print("Backend is healthy!")
        break

print("\n=== Step 4: Run migration ===")
out, ec = run(f"docker exec {DEPLOY_ID}-backend python /app/migrations/migration_bucket_replace_20260604.py -y 2>&1", timeout=120)
print(out)
print(f"Exit code: {ec}")

print("\n=== Step 5: Verify ===")
out, ec = run(f"curl -sk https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/api/health 2>&1")
print(f"HTTPS Health: {out.strip()[:200]}")

client.close()
print("\nDone!")
