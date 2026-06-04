import paramiko, sys, time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"

SCRIPT = f"""
set -e
cd {PROJ}
echo '=== git fetch/reset ==='
timeout 60 git fetch origin master --no-tags || echo 'fetch warn'
git reset --hard origin/master
git log -1 --oneline
echo '=== BUILD_COMMIT ==='
BUILD_COMMIT=$(git log -1 --format=%H)
export BUILD_COMMIT
grep -q '^BUILD_COMMIT=' .env 2>/dev/null && sed -i "s|^BUILD_COMMIT=.*|BUILD_COMMIT=$BUILD_COMMIT|" .env || echo "BUILD_COMMIT=$BUILD_COMMIT" >> .env
echo "BUILD_COMMIT=$BUILD_COMMIT"
echo '=== build h5 (no-cache) ==='
docker compose -f docker-compose.prod.yml build --no-cache h5-web
echo '=== up h5 ==='
docker compose -f docker-compose.prod.yml up -d h5-web
echo '=== wait ==='
sleep 8
docker compose -f docker-compose.prod.yml ps h5-web
echo '=== reconnect gateway ==='
docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true
docker exec gateway-nginx nginx -s reload 2>/dev/null || true
echo '=== DONE ==='
"""

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)
chan = cli.get_transport().open_session()
chan.exec_command(SCRIPT)
chan.settimeout(1200)
buf = b""
import select
while True:
    if chan.recv_ready():
        data = chan.recv(4096)
        if not data:
            break
        sys.stdout.write(data.decode("utf-8", "ignore"))
        sys.stdout.flush()
    if chan.exit_status_ready() and not chan.recv_ready():
        break
    time.sleep(0.5)
# drain
while chan.recv_ready():
    sys.stdout.write(chan.recv(4096).decode("utf-8", "ignore"))
err = chan.recv_stderr(65535).decode("utf-8", "ignore")
if err.strip():
    sys.stdout.write("\n=== STDERR ===\n" + err)
print("\nexit:", chan.recv_exit_status())
cli.close()
