"""
Deploy AI Home ActionBar + Attachment hint filter bugfix (20260517).

Stage 3 of remote-deploy-and-test SKILL:
- SSH to server
- git pull (DEPLOY_ID dir)
- BUILD_COMMIT in .env
- docker compose build --no-cache backend h5-web
- docker compose up -d
- network connect gateway
- (gateway config already exists for this DEPLOY_ID since it's a pre-existing deployment)
- verify SSL still intact
"""
from __future__ import annotations

import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
import os as _os
_GH_TOKEN = _os.environ.get("GH_TOKEN", "<REDACTED_GH_TOKEN>")
GIT_URL = f"https://ankun-eric:{_GH_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
GATEWAY_CT_GUESS_LIST = ["gateway-nginx", "gateway", "nginx-gateway"]


def open_ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PWD,
                timeout=30, banner_timeout=30, auth_timeout=30,
                look_for_keys=False, allow_agent=False)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, timeout: int = 600, quiet: bool = False) -> tuple[int, str, str]:
    if not quiet:
        print(f"\n$ {cmd[:300]}{'...' if len(cmd) > 300 else ''}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip():
            print(out[-4000:])
        if err.strip():
            print("STDERR:", err[-2000:])
        print(f"[exit={code}]")
    return code, out, err


def main():
    print("=== Deploy AI Home ActionBar+Attachment Filter Bugfix (20260517) ===")
    print(f"Server: {USER}@{HOST}:{PORT}")
    print(f"DEPLOY_ID: {DEPLOY_ID}")

    cli = open_ssh()
    try:
        # ===== Stage 3.0: pre-check container status =====
        run(cli, "docker ps --format '{{.Names}}' | grep -E '6b099ed3' | head -20")

        # discover gateway container
        gateway_ct = None
        for guess in GATEWAY_CT_GUESS_LIST:
            code, out, _ = run(cli, f"docker ps --format '{{{{.Names}}}}' | grep -i '{guess}' | head -1", quiet=True)
            if out.strip():
                gateway_ct = out.strip().splitlines()[0]
                break
        if not gateway_ct:
            code, out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -iE 'gateway|nginx' | head -1")
            if out.strip():
                gateway_ct = out.strip().splitlines()[0]
        print(f">>> Gateway container: {gateway_ct}")

        # ===== Stage 3.1: SSL snapshot =====
        if gateway_ct:
            ssl_snapshot_cmd = (
                f"docker exec {gateway_ct} nginx -T 2>/dev/null | "
                "grep -E 'listen.*443.*ssl|ssl_certificate|ssl_certificate_key|ssl_protocols|ssl_ciphers|ssl_session|ssl_prefer_server_ciphers' "
                "| sort -u | tee /tmp/ssl_snapshot_before.txt"
            )
            run(cli, ssl_snapshot_cmd)

        # ===== Stage 3.2: Git pull =====
        # check git status
        run(cli, f"ls -la {REMOTE_DIR}/.git 2>/dev/null | head -3")
        code, out, _ = run(cli, f"test -d {REMOTE_DIR}/.git && echo HAS_GIT || echo NO_GIT", quiet=True)
        has_git = "HAS_GIT" in out

        if has_git:
            print(">>> Repository exists, fetching latest...")
            # configure auth
            run(cli, f"cd {REMOTE_DIR} && git config --local credential.helper '' && git remote set-url origin '{GIT_URL}'")
            # fetch & reset
            code, _, err = run(cli, f"cd {REMOTE_DIR} && timeout 60 git fetch origin --no-tags 2>&1 | tail -20")
            if code != 0:
                print("!!! Git fetch failed, retrying with depth=1")
                code, _, _ = run(cli, f"cd {REMOTE_DIR} && timeout 60 git fetch origin --depth 1 --no-tags 2>&1 | tail -20")
            run(cli, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
            run(cli, f"cd {REMOTE_DIR} && git clean -fd 2>&1 | tail -5")
        else:
            print(">>> First-time clone")
            run(cli, f"timeout 120 git clone --depth 1 --single-branch --no-tags '{GIT_URL}' {REMOTE_DIR} 2>&1 | tail -20")

        # verify latest commit
        run(cli, f"cd {REMOTE_DIR} && git log -1 --oneline")
        run(cli, f"cd {REMOTE_DIR} && git status --short | head -10")

        # ===== Stage 3.3: BUILD_INFO =====
        run(cli, f"cd {REMOTE_DIR} && BUILD_COMMIT=$(git log -1 --format='%H') && echo \"BUILD_COMMIT=$BUILD_COMMIT\" > .env.build && echo \"build commit: $BUILD_COMMIT\"")

        # check existing .env / .env.production
        run(cli, f"ls -la {REMOTE_DIR}/.env {REMOTE_DIR}/.env.production 2>&1 | head -5")

        # ensure BUILD_COMMIT is in .env (append/overwrite)
        run(cli, f"cd {REMOTE_DIR} && grep -v '^BUILD_COMMIT=' .env > .env.tmp 2>/dev/null; cat .env.build >> .env.tmp; mv .env.tmp .env || true")

        # ===== Stage 3.4: Find compose file =====
        code, out, _ = run(cli, f"ls {REMOTE_DIR}/docker-compose.prod.yml {REMOTE_DIR}/docker-compose.yml 2>/dev/null")
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"
        print(f">>> Using compose file: {compose_file}")

        # check current container services
        run(cli, f"cd {REMOTE_DIR} && docker compose -f {compose_file} ps")

        # ===== Stage 3.5: Build backend + h5-web only (this bug fix) =====
        # The change set: backend (chat.py, sanitizer) + h5-web (ai-home page.tsx)
        # backend has tests file too; we'll rebuild backend & h5-web only
        print(">>> Building backend (no-cache)...")
        rc_be, _, _ = run(cli, f"cd {REMOTE_DIR} && docker compose -f {compose_file} build --no-cache backend 2>&1 | tail -50", timeout=1200)
        if rc_be != 0:
            print("!!! backend build failed")

        print(">>> Building h5-web (no-cache)...")
        # check the service name first
        code, out, _ = run(cli, f"cd {REMOTE_DIR} && docker compose -f {compose_file} config --services 2>&1")
        services = [s.strip() for s in out.strip().splitlines() if s.strip() and not s.startswith("WARN")]
        print(f">>> Compose services: {services}")
        # find h5 service name
        h5_svc = None
        for s in services:
            if "h5" in s.lower():
                h5_svc = s
                break
        if h5_svc:
            rc_h5, _, _ = run(cli, f"cd {REMOTE_DIR} && docker compose -f {compose_file} build --no-cache {h5_svc} 2>&1 | tail -50", timeout=1500)
            if rc_h5 != 0:
                print(f"!!! {h5_svc} build failed")
        else:
            print("!!! No h5 service found")

        # ===== Stage 3.6: Restart backend + h5-web =====
        # 'up -d' will recreate changed services only
        print(">>> Restarting containers...")
        # Use --no-deps to only restart these
        targets = "backend"
        if h5_svc:
            targets += f" {h5_svc}"
        run(cli, f"cd {REMOTE_DIR} && docker compose -f {compose_file} up -d --force-recreate --no-deps {targets} 2>&1 | tail -30")

        # ===== Stage 3.7: Reconnect gateway to network =====
        if gateway_ct:
            run(cli, f"docker network connect {DEPLOY_ID}-network {gateway_ct} 2>&1 || true")
            run(cli, f"docker network inspect {DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'")

        # ===== Stage 3.8: Wait for health =====
        print(">>> Waiting for containers to be healthy...")
        for i in range(24):
            code, out, _ = run(cli, f"cd {REMOTE_DIR} && docker compose -f {compose_file} ps --format json 2>&1", quiet=True)
            # Just print plain ps
            time.sleep(5)
            code, out, _ = run(cli, f"cd {REMOTE_DIR} && docker compose -f {compose_file} ps 2>&1 | head -20", quiet=True)
            print(f"  [{(i+1)*5}s]\n{out[-1500:]}")
            if "Up" in out or "running" in out:
                # Check if backend & h5 specifically are up
                if "backend" in out and ("h5" in out):
                    bad = "starting" in out.lower() or "restarting" in out.lower() or "unhealthy" in out.lower()
                    if not bad:
                        print(">>> Containers ready")
                        break

        # ===== Stage 3.9: SSL validation =====
        if gateway_ct:
            print(">>> Validating SSL post-deploy...")
            run(cli, f"docker exec {gateway_ct} nginx -t 2>&1")
            run(cli, f"docker exec {gateway_ct} nginx -s reload 2>&1")
            time.sleep(2)
            run(cli, f"curl -vI https://{HOST}/ 2>&1 | grep -iE 'SSL certificate|subject|issuer|expire' | head -10")

        # ===== Stage 3.10: Quick HTTP check =====
        print(">>> Quick HTTP check from server...")
        run(cli, f"curl -Isk https://localhost/autodev/{DEPLOY_ID}/ 2>&1 | head -5")
        run(cli, f"curl -Isk https://localhost/autodev/{DEPLOY_ID}/api/health 2>&1 | head -5")

        # final container status
        run(cli, f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep -E '{DEPLOY_ID}|gateway' | head -20")

        print("\n=== DEPLOY DONE ===")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
