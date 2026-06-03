"""Remote redeploy script for newbb.test.bangbangvip.com (robust version)
DEPLOY_ID: 6b099ed3-7175-4a78-91f4-44570c84ed27
Long-running steps (build / up) run in nohup background on server, with progress
tailed via short-lived SSH commands to avoid transport-level timeouts.
"""
from __future__ import annotations
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
GIT_URL = "https://ankun-eric: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@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BRANCH = "master"

REMOTE_LOG = f"{PROJECT_DIR}/_redeploy_remote.log"
REMOTE_DONE = f"{PROJECT_DIR}/_redeploy.done"
REMOTE_BUILD_SCRIPT = f"{PROJECT_DIR}/_remote_build.sh"


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(
        HOST,
        port=PORT,
        username=USER,
        password=PASSWORD,
        timeout=60,
        banner_timeout=60,
        auth_timeout=60,
        look_for_keys=False,
        allow_agent=False,
    )
    return cli


def sq(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def run(cli, cmd, *, timeout=180, sudo=False, check=True, quiet=False):
    full = cmd
    if sudo:
        full = f"echo {sq(PASSWORD)} | sudo -S bash -lc {sq(cmd)}"
    if not quiet:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = cli.exec_command(full, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip():
            print(out[-3500:])
        if err.strip():
            print(f"[stderr] {err[-1500:]}")
        print(f"[rc={rc}]")
    if check and rc != 0:
        raise RuntimeError(f"cmd failed rc={rc}: {cmd}")
    return rc, out, err


def upload_remote_build_script(cli):
    """Create a script on the server that runs the entire build+up sequence, with logs."""
    script = f"""#!/usr/bin/env bash
set -o pipefail
exec > >(tee -a {REMOTE_LOG}) 2>&1
cd {PROJECT_DIR}
echo "===== remote build started: $(date -Is) ====="
BUILD_COMMIT=$(git log -1 --format=%H)
export BUILD_COMMIT
echo "BUILD_COMMIT=$BUILD_COMMIT"

echo "--- docker compose down ---"
docker compose -f docker-compose.prod.yml down --remove-orphans || true

echo "--- docker compose build --no-cache ---"
docker compose -f docker-compose.prod.yml build --no-cache
RC_BUILD=$?
echo "build rc=$RC_BUILD"
if [ $RC_BUILD -ne 0 ]; then
  echo "===== BUILD FAILED ====="
  echo "FAIL" > {REMOTE_DONE}
  exit 1
fi

echo "--- docker compose up -d ---"
docker compose -f docker-compose.prod.yml up -d
RC_UP=$?
echo "up rc=$RC_UP"
if [ $RC_UP -ne 0 ]; then
  echo "===== UP FAILED ====="
  echo "FAIL" > {REMOTE_DONE}
  exit 1
fi

echo "--- waiting for containers ready ---"
for i in $(seq 1 36); do
  STATUSES=$(docker compose -f docker-compose.prod.yml ps --format '{{{{.Name}}}} {{{{.State}}}} {{{{.Status}}}}' 2>&1)
  echo "[$((i*5))s] $STATUSES" | tr '\\n' '|'
  echo
  STARTING=$(echo "$STATUSES" | grep -c -i 'starting' || true)
  UNHEALTHY=$(echo "$STATUSES" | grep -c -i 'unhealthy' || true)
  RUNNING=$(echo "$STATUSES" | grep -c -i 'running' || true)
  TOTAL=$(echo "$STATUSES" | grep -cv '^$' || true)
  if [ "$STARTING" = "0" ] && [ "$UNHEALTHY" = "0" ] && [ "$RUNNING" -ge "4" ]; then
    echo "all ready (running=$RUNNING/$TOTAL)"
    break
  fi
  sleep 5
done

echo "--- final status ---"
docker compose -f docker-compose.prod.yml ps

echo "===== remote build finished OK: $(date -Is) ====="
echo "OK" > {REMOTE_DONE}
"""
    sftp = cli.open_sftp()
    with sftp.file(REMOTE_BUILD_SCRIPT, "w") as f:
        f.write(script)
    sftp.chmod(REMOTE_BUILD_SCRIPT, 0o755)
    sftp.close()


def tail_remote(cli, n=80):
    rc, out, _ = run(cli, f"tail -n {n} {REMOTE_LOG} 2>/dev/null || true", check=False, quiet=True)
    return out


def main():
    print(f"=== Connecting to {USER}@{HOST}:{PORT} ===")
    cli = ssh_connect()
    keepalive = cli.get_transport()
    keepalive.set_keepalive(30)

    print("\n=== Step 1: Verify host & docker ===")
    run(cli, "uname -a && docker --version && docker compose version")

    print("\n=== Step 2: Sync project code from Git ===")
    rc, out, _ = run(cli, f"test -d {PROJECT_DIR}/.git && echo HAS_GIT || echo NEED_CLONE", check=False)
    if "HAS_GIT" in out:
        print("[*] Project repo exists, fetch+reset to origin/master")
        run(cli, f"cd {PROJECT_DIR} && timeout 90 git fetch --depth 1 --no-tags origin {BRANCH}", timeout=120)
        run(cli, f"cd {PROJECT_DIR} && git reset --hard FETCH_HEAD && git clean -fd -e .env -e .env.production -e .env.build -e _* -e mysql_data -e uploads_data")
    else:
        print("[*] Project repo missing, clone fresh")
        run(cli, f"rm -rf {PROJECT_DIR}", sudo=True, check=False)
        run(cli, f"timeout 180 git clone --depth 1 --single-branch --branch {BRANCH} --no-tags {GIT_URL} {PROJECT_DIR}", timeout=240)

    run(cli, f"cd {PROJECT_DIR} && git log -1 --oneline")

    print("\n=== Step 3: Prep BUILD_COMMIT & .env ===")
    run(cli, f"cd {PROJECT_DIR} && BUILD_COMMIT=$(git log -1 --format=%H) && echo BUILD_COMMIT=$BUILD_COMMIT > .env.build && (grep -v '^BUILD_COMMIT=' .env 2>/dev/null > .env.tmp || true) && (test -f .env.tmp && mv -f .env.tmp .env || touch .env) && echo BUILD_COMMIT=$BUILD_COMMIT >> .env && echo done")

    print("\n=== Step 4: Upload remote build script ===")
    upload_remote_build_script(cli)
    run(cli, f"rm -f {REMOTE_DONE} {REMOTE_LOG} && ls -la {REMOTE_BUILD_SCRIPT}")

    print("\n=== Step 5: Launch build in background (setsid+nohup, detached) ===")
    # Use setsid to fully detach process from session and SSH channel
    launch_cmd = (
        f"cd {PROJECT_DIR} && "
        f"setsid nohup bash {REMOTE_BUILD_SCRIPT} </dev/null >/dev/null 2>&1 & "
        f"disown 2>/dev/null || true; echo launched"
    )
    # Use a short timeout so even if channel hangs we don't block forever
    ch = cli.get_transport().open_session()
    ch.set_combine_stderr(True)
    ch.exec_command(launch_cmd)
    # Read what we can; close after a brief read window
    end = time.time() + 8
    buf = b""
    while time.time() < end:
        if ch.recv_ready():
            buf += ch.recv(4096)
        if ch.exit_status_ready():
            break
        time.sleep(0.5)
    print(buf.decode(errors="replace") or "[no immediate output, expected]")
    try:
        ch.close()
    except Exception:
        pass
    # Verify process started by checking ps
    time.sleep(2)
    run(cli, f"pgrep -f _remote_build.sh || echo no_pid", check=False)

    print("\n=== Step 6: Poll remote log until done ===")
    last_size = 0
    deadline = time.time() + 60 * 35
    while time.time() < deadline:
        time.sleep(15)
        rc, done_out, _ = run(cli, f"cat {REMOTE_DONE} 2>/dev/null || echo NOT_DONE", check=False, quiet=True)
        size_rc, size_out, _ = run(cli, f"wc -c < {REMOTE_LOG} 2>/dev/null || echo 0", check=False, quiet=True)
        try:
            size_now = int(size_out.strip().splitlines()[-1])
        except Exception:
            size_now = 0
        if size_now > last_size:
            tail_text = tail_remote(cli, n=40)
            print(f"\n--- [+{size_now - last_size}B] tail ---\n{tail_text[-2500:]}")
            last_size = size_now
        else:
            print(f"[poll] no new output (size={size_now}); done flag={done_out.strip()[:30]}")
        if "OK" in done_out:
            print("\n[+] Remote build finished OK")
            break
        if "FAIL" in done_out:
            print("\n[!] Remote build FAILED")
            raise RuntimeError("Remote build failed; see remote log above")
    else:
        raise RuntimeError("Remote build timed out (>35min)")

    print("\n=== Step 7: Identify gateway container ===")
    rc, out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -iE 'gateway|nginx' | head -5", check=False)
    gw_candidates = [x.strip() for x in out.strip().splitlines() if x.strip()]
    gateway_name = None
    for cand in gw_candidates:
        if "gateway" in cand.lower():
            gateway_name = cand
            break
    if not gateway_name and gw_candidates:
        gateway_name = gw_candidates[0]
    print(f"[+] Gateway container: {gateway_name}")
    if not gateway_name:
        raise RuntimeError("No gateway container found on server")

    print("\n=== Step 8: Connect gateway to project network ===")
    run(cli, f"docker network connect {DEPLOY_ID}-network {gateway_name} 2>&1 || true", check=False)
    run(cli, f"docker network inspect {DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'")

    print("\n=== Step 9: Install gateway route conf into conf.d ===")
    confd_host_dir = "/home/ubuntu/gateway/conf.d"
    confd_path = f"{confd_host_dir}/{DEPLOY_ID}.conf"
    rc, out, _ = run(cli, f"test -d {confd_host_dir} && echo HAS || echo MISSING", check=False)
    if "MISSING" in out:
        print("[*] gateway conf.d missing on host; trying to find gateway dir layout")
        run(cli, "ls -la /home/ubuntu/gateway/ 2>/dev/null | head -30", check=False)
    run(cli, f"mkdir -p {confd_host_dir}", sudo=True, check=False)
    run(cli, f"cp {PROJECT_DIR}/gateway-routes.conf {confd_path}", sudo=True)
    run(cli, f"ls -la {confd_path}")

    # check the gateway container actually loads conf.d/*.conf
    rc, out, _ = run(cli, f"docker exec {gateway_name} sh -c 'grep -R include /etc/nginx/nginx.conf 2>/dev/null | head -10'", check=False)

    print("\n=== Step 10: Test & reload gateway nginx ===")
    rc, out, err = run(cli, f"docker exec {gateway_name} nginx -t", check=False)
    if rc != 0:
        print("[!] nginx -t failed; dumping route file for debugging")
        run(cli, f"docker exec {gateway_name} cat /etc/nginx/conf.d/{DEPLOY_ID}.conf 2>/dev/null | head -100", check=False)
        raise RuntimeError("nginx -t failed")
    run(cli, f"docker exec {gateway_name} nginx -s reload")

    print("\n=== Step 11: Final container status ===")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps")

    print("\n=== Step 12: Local on-server smoke checks ===")
    base = f"https://localhost/autodev/{DEPLOY_ID}"
    for path, label in [
        ("/api/health", "backend health"),
        ("/", "h5 frontend root"),
        ("/admin/", "admin frontend"),
    ]:
        run(cli, f"curl -sk -o /dev/null -w '{label} {path} -> %{{http_code}}\\n' --max-time 20 {base}{path}", check=False)

    cli.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FATAL] {e}", file=sys.stderr)
        sys.exit(1)
