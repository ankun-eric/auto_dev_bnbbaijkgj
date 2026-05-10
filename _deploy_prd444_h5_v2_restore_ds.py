"""恢复 PRD-443 的 design-system-v2/ 静态资源进入 H5 容器（避免回归 404）"""
import time
from pathlib import Path
import urllib.request
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

ROOT = Path(__file__).resolve().parent
LOCAL_DIR = ROOT / "h5-web" / "public" / "design-system-v2"
REMOTE_TMP = f"/tmp/design-system-v2-{int(time.time())}"
CONTAINER = f"{DEPLOY_ID}-h5"
CONTAINER_PATH = "/app/public/design-system-v2"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"\n$ {cmd[:140]}\n[rc={rc}] {out[:600]}")
    if err:
        print("ERR:", err[:400])
    return rc

# upload via sftp
sftp = ssh.open_sftp()
run(f"mkdir -p {REMOTE_TMP}")
for f in LOCAL_DIR.iterdir():
    if f.is_file():
        sftp.put(str(f), f"{REMOTE_TMP}/{f.name}")
        print(f"uploaded {f.name}")
sftp.close()

run(f"docker exec {CONTAINER} mkdir -p {CONTAINER_PATH}")
run(f"docker cp {REMOTE_TMP}/. {CONTAINER}:{CONTAINER_PATH}/")
run(f"docker exec {CONTAINER} ls {CONTAINER_PATH}")
run(f"docker restart {CONTAINER}")
print("waiting 30s for container...")
time.sleep(30)
run(f"docker ps --filter name={CONTAINER} --format '{{{{.Status}}}}'")

# smoke
checks = [
    "/",
    "/home/",
    "/ai-home/",
    "/design-system-v2/index.html",
    "/design-system-v2/design-tokens.css",
]
ok_count = 0
for p in checks:
    url = BASE_URL + p
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            print(f"  {url}  → {r.getcode()}")
            if r.getcode() == 200:
                ok_count += 1
    except Exception as e:
        print(f"  {url}  → ERROR {e}")

print(f"\n[smoke] {ok_count}/{len(checks)} PASS")
ssh.close()
