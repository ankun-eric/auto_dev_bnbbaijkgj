"""Sync changed files since ad9f585 from local to server, then rebuild containers."""
import os
import sys
import time
import tarfile
import io
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

# Changed files between ad9f585..9a9c655 (server is at ad9f585, local at 9a9c655)
CHANGED_FILES = [
    "admin-web/src/app/(admin)/audit/center/page.tsx",
    "admin-web/src/app/(admin)/audit/phones/page.tsx",
    "admin-web/src/app/(admin)/layout.tsx",
    "admin-web/src/app/(admin)/product-system/coupons/page.tsx",
    "admin-web/src/app/(admin)/product-system/new-user-coupons/page.tsx",
    "admin-web/src/app/(admin)/product-system/partners/page.tsx",
    "backend/app/api/audit.py",
    "backend/app/api/auth.py",
    "backend/app/api/coupons.py",
    "backend/app/api/coupons_admin.py",
    "backend/app/api/favorites.py",
    "backend/app/api/third_party_openapi.py",
    "backend/app/main.py",
    "backend/app/models/models.py",
    "backend/app/schemas/audit.py",
    "backend/app/schemas/coupons.py",
    "h5-web/src/app/my-coupons/page.tsx",
    "h5-web/src/app/product/[id]/page.tsx",
    "h5-web/src/app/tcm/page.tsx",
]

# Also push deploy configs
CONFIG_FILES = [
    "docker-compose.prod.yml",
    "gateway-routes.conf",
    "backend/Dockerfile",
    "admin-web/Dockerfile",
    "h5-web/Dockerfile",
]


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


def make_tarball(local_root, files):
    """Create an in-memory tar.gz of the files preserving relative paths."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in files:
            full = os.path.join(local_root, rel.replace("/", os.sep))
            if os.path.exists(full):
                tar.add(full, arcname=rel)
            else:
                print(f"  [warn] missing: {rel}")
    buf.seek(0)
    return buf.getvalue()


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c = connect()
    print(f"Connected to {HOST}")

    # 1. Sync changed source files via tar
    print("\n=== Step 1: Sync changed source files ===")
    all_files = CHANGED_FILES + CONFIG_FILES
    tar_bytes = make_tarball(local_root, all_files)
    remote_tar = f"/tmp/{DEPLOY_ID}-sync.tar.gz"
    sftp = c.open_sftp()
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_bytes)
    sftp.close()
    print(f"  uploaded {len(tar_bytes)} bytes to {remote_tar}")
    # Extract on server (overwrite)
    run(c, f"cd {PROJECT_DIR} && tar -xzf {remote_tar} && rm -f {remote_tar}", check=True)

    # Sanity check: verify a known new file exists
    run(c, f"ls -la {PROJECT_DIR}/backend/app/api/audit.py {PROJECT_DIR}/backend/app/api/coupons_admin.py {PROJECT_DIR}/backend/app/api/third_party_openapi.py 2>&1")
    run(c, f"head -3 {PROJECT_DIR}/backend/app/api/audit.py")

    # 2. Rebuild relevant services
    print("\n=== Step 2: docker compose build (no-cache backend, regular for next.js) ===")
    # backend Python: use cache (pip layer reuses) – but source copy step will refresh code
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build 2>&1 | tail -30", timeout=1500, check=True)

    print("\n=== Step 3: docker compose up -d (recreate) ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate 2>&1 | tail -30", timeout=180, check=True)

    print("\n=== Step 4: Wait for containers ===")
    time.sleep(20)
    for i in range(10):
        out, _, _ = run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")
        if out.count(DEPLOY_ID) >= 4 and "Restarting" not in out:
            break
        time.sleep(8)

    # 5. Reconnect gateway to network
    print("\n=== Step 5: Connect gateway to project network ===")
    run(c, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")
    run(c, f"docker network inspect {DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'")

    # 6. Update gateway conf.d - merge our routes with preserved static blocks
    print("\n=== Step 6: Update gateway conf.d (preserve downloads/apk) ===")
    run(c, f"cp {GATEWAY_CONF} {GATEWAY_CONF}.bak.$(date +%Y%m%d%H%M%S) 2>&1 || true")
    # SSL snapshot
    run(c, f"docker exec gateway nginx -T 2>/dev/null | grep -E 'ssl_certificate|listen.*443.*ssl' | sort -u > /tmp/ssl_before.txt && cat /tmp/ssl_before.txt")

    # Read current conf and extract balanced location blocks for downloads & apk
    out, _, _ = run(c, f"cat {GATEWAY_CONF}", quiet=True)

    def extract_balanced_block(text, location_path):
        """Extract a complete location block with balanced braces."""
        idx = text.find(f"location {location_path}")
        if idx == -1:
            return None
        brace_start = text.find("{", idx)
        if brace_start == -1:
            return None
        depth = 0
        i = brace_start
        while i < len(text):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[idx:i+1]
            i += 1
        return None

    extra_blocks = []
    for path in [f"/autodev/{DEPLOY_ID}/downloads/", f"/autodev/{DEPLOY_ID}/apk/"]:
        blk = extract_balanced_block(out, path)
        if blk:
            extra_blocks.append(f"# Preserved: {path}\n{blk}")

    # Read local routes
    local_routes_path = os.path.join(local_root, "gateway-routes.conf")
    with open(local_routes_path, "r", encoding="utf-8") as f:
        local_routes = f.read()

    # Compose final conf — put extra blocks before the broad H5 catch-all if possible.
    # Simpler: append at end (nginx longest-prefix matching wins).
    final_conf = local_routes.rstrip() + "\n\n# ===== Preserved static locations =====\n" + "\n\n".join(extra_blocks) + "\n"

    # Upload via sftp
    sftp = c.open_sftp()
    with sftp.open(GATEWAY_CONF, "w") as f:
        f.write(final_conf)
    sftp.close()
    print(f"  wrote new {GATEWAY_CONF}")

    # 7. Test and reload
    print("\n=== Step 7: nginx -t & reload ===")
    out, err, code = run(c, "docker exec gateway nginx -t 2>&1")
    if code != 0:
        print("nginx -t FAILED, restoring most recent backup")
        run(c, f"ls -t {GATEWAY_CONF}.bak.* | head -1 | xargs -I{{}} cp {{}} {GATEWAY_CONF}")
        run(c, "docker exec gateway nginx -t 2>&1")
        sys.exit(1)
    run(c, "docker exec gateway nginx -s reload 2>&1")
    time.sleep(3)

    # SSL verify
    print("\n=== Step 8: SSL diff & connectivity ===")
    run(c, f"docker exec gateway nginx -T 2>/dev/null | grep -E 'ssl_certificate|listen.*443.*ssl' | sort -u > /tmp/ssl_after.txt && diff /tmp/ssl_before.txt /tmp/ssl_after.txt && echo SSL_OK || echo SSL_DIFF")
    run(c, f"curl -sI https://{DOMAIN}/ 2>&1 | head -5")

    print("\n=== Step 9: Final container status ===")
    run(c, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

    c.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    main()
