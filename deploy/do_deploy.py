"""Remote deploy orchestration for bini-health.

Performs:
  1. SSH connect, git fetch+reset to origin/master on server
  2. Sync local config files (docker-compose.prod.yml, gateway-routes.conf, Dockerfile updates) via SFTP
  3. docker compose down + build + up
  4. Wait for healthchecks
  5. Reconnect gateway to new project network
  6. Update gateway conf.d/<DEPLOY_ID>.conf preserving extra static locations
  7. nginx -t -> reload -> SSL verify
"""
import os
import sys
import time
import paramiko
import posixpath

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_DIR = "/home/ubuntu/gateway"
GATEWAY_CONF = f"{GATEWAY_DIR}/conf.d/{DEPLOY_ID}.conf"
GIT_USER = os.environ.get("GIT_USER", "ankun-eric")
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=600, check=False, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out:
            print(out[-3000:])
        if err:
            print(f"[stderr] {err[-1500:]}")
        print(f"[exit {code}]")
    if check and code != 0:
        raise RuntimeError(f"Command failed (exit {code}): {cmd}\n{err}")
    return out, err, code


def upload(c, local, remote):
    print(f"  upload {local} -> {remote}")
    sftp = c.open_sftp()
    try:
        # ensure remote dir exists
        rdir = posixpath.dirname(remote)
        if rdir:
            try:
                sftp.stat(rdir)
            except FileNotFoundError:
                sftp.mkdir(rdir)
        sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    c = connect()
    print(f"Connected to {HOST}")

    # 1. Git update
    print("\n=== Step 1: Git update ===")
    run(c, f"test -d {PROJECT_DIR}/.git && echo HAS_GIT || echo NO_GIT")
    out, _, _ = run(c, f"test -d {PROJECT_DIR}/.git && echo Y || echo N", quiet=True)
    if out.strip() == "Y":
        # Configure git to be patient with slow GitHub
        run(c, f"cd {PROJECT_DIR} && git config http.lowSpeedLimit 0 && git config http.lowSpeedTime 999999 && git config http.postBuffer 524288000 && git remote set-url origin {GIT_URL}")
        # Try fetch with retry
        ok = False
        for attempt in range(3):
            print(f"  git fetch attempt {attempt+1}/3 ...")
            _, _, code = run(c, f"cd {PROJECT_DIR} && timeout 600 git fetch origin master 2>&1 | tail -5", timeout=650)
            if code == 0:
                ok = True
                break
            time.sleep(5)
        if not ok:
            raise RuntimeError("git fetch failed after 3 attempts")
        run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master && git clean -fd", check=True)
    else:
        run(c, f"rm -rf {PROJECT_DIR} && git clone {GIT_URL} {PROJECT_DIR}", check=True, timeout=900)
    run(c, f"cd {PROJECT_DIR} && git log -1 --oneline")

    # 2. Re-upload local config files (in case they're not in git or differ)
    print("\n=== Step 2: Sync deploy config files ===")
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files_to_upload = [
        ("docker-compose.prod.yml", f"{PROJECT_DIR}/docker-compose.prod.yml"),
        ("gateway-routes.conf", f"{PROJECT_DIR}/gateway-routes.conf"),
        ("backend/Dockerfile", f"{PROJECT_DIR}/backend/Dockerfile"),
        ("admin-web/Dockerfile", f"{PROJECT_DIR}/admin-web/Dockerfile"),
        ("h5-web/Dockerfile", f"{PROJECT_DIR}/h5-web/Dockerfile"),
    ]
    for local_rel, remote in files_to_upload:
        local_full = os.path.join(local_root, local_rel)
        if os.path.exists(local_full):
            upload(c, local_full, remote)

    # 3. Docker compose down/build/up
    print("\n=== Step 3: docker compose build & up ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1 | tail -20", timeout=120)
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build 2>&1 | tail -80", timeout=1500, check=True)
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1 | tail -30", timeout=180, check=True)

    # 4. Wait for containers
    print("\n=== Step 4: Wait for containers (60s) ===")
    time.sleep(20)
    for i in range(8):
        out, _, _ = run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")
        if out.count(DEPLOY_ID) >= 4 and "Restarting" not in out:
            break
        time.sleep(10)

    # 5. Reconnect gateway to new network
    print("\n=== Step 5: Connect gateway to project network ===")
    run(c, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")
    run(c, f"docker network inspect {DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'")

    # 6. Update gateway conf.d - preserve existing extra blocks (downloads/, apk/) by checking current file
    print("\n=== Step 6: Update gateway conf.d ===")
    # Backup
    run(c, f"cp {GATEWAY_CONF} {GATEWAY_CONF}.bak.$(date +%Y%m%d%H%M%S) 2>&1 || true")
    # SSL snapshot
    run(c, f"docker exec gateway nginx -T 2>/dev/null | grep -E 'ssl_certificate|listen.*443.*ssl' | sort -u > /tmp/ssl_before.txt && cat /tmp/ssl_before.txt")
    # Read current conf to preserve extra blocks (downloads, apk)
    out, _, _ = run(c, f"cat {GATEWAY_CONF}", quiet=True)
    extra_blocks = []
    # crude extraction: find downloads/ and apk/ static location blocks
    if "/downloads/" in out:
        # Extract the downloads block
        import re
        m = re.search(r"# \u9759\u6001\u6587\u4ef6\u4e0b\u8f7d.*?\nlocation /autodev/[^/]+/downloads/ \{[^}]+\}", out, re.S)
        if not m:
            m = re.search(r"location /autodev/[^/]+/downloads/ \{[^}]+\}", out, re.S)
        if m:
            extra_blocks.append("# 静态文件下载\n" + m.group(0).split("location ", 1)[-1] if not m.group(0).startswith("#") else m.group(0))
    if "/apk/" in out:
        import re
        m = re.search(r"location /autodev/[^/]+/apk/ \{[^}]+\}", out, re.S)
        if m:
            extra_blocks.append("# APK 下载\nlocation " + m.group(0).split("location ", 1)[-1])

    # Upload local gateway-routes.conf
    upload(c, os.path.join(local_root, "gateway-routes.conf"), GATEWAY_CONF)

    # Append extra blocks if found
    if extra_blocks:
        extra_text = "\n\n# ===== Preserved static locations =====\n" + "\n\n".join(extra_blocks) + "\n"
        # Write via a here-doc using base64 to avoid quoting issues
        import base64
        b64 = base64.b64encode(extra_text.encode()).decode()
        run(c, f"echo '{b64}' | base64 -d >> {GATEWAY_CONF}")

    # 7. nginx -t and reload
    print("\n=== Step 7: nginx -t & reload ===")
    out, err, code = run(c, "docker exec gateway nginx -t 2>&1")
    if code != 0:
        print("nginx -t FAILED, restoring backup")
        run(c, f"ls -t {GATEWAY_CONF}.bak.* | head -1 | xargs -I{{}} cp {{}} {GATEWAY_CONF}")
        run(c, "docker exec gateway nginx -t 2>&1")
        sys.exit(1)
    run(c, "docker exec gateway nginx -s reload 2>&1")
    time.sleep(2)

    # SSL snapshot after
    run(c, f"docker exec gateway nginx -T 2>/dev/null | grep -E 'ssl_certificate|listen.*443.*ssl' | sort -u > /tmp/ssl_after.txt && diff /tmp/ssl_before.txt /tmp/ssl_after.txt && echo 'SSL_OK'")

    # 8. Container final status
    print("\n=== Step 8: Final container status ===")
    run(c, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}'")
    run(c, f"docker compose -f {PROJECT_DIR}/docker-compose.prod.yml -p {DEPLOY_ID.split('-')[0]} ps 2>&1 || cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps")

    # 9. SSL terminal verify
    print("\n=== Step 9: SSL verify ===")
    run(c, f"curl -sI https://{DOMAIN}/ 2>&1 | head -5")

    c.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    main()
