"""PRD-448 咨询人胶囊（AdvisorCapsule）改造部署脚本

仅改动 h5-web 前端。由于服务器到 GitHub 网络不稳定，采用本地打 tar 上传方案：
- 本地打 h5-web/src 的 tar.gz
- SFTP 上传到服务器
- 解压覆盖 h5-web/src
- docker compose build h5-web + up -d h5-web
- smoke 测试关键页面
"""
from __future__ import annotations

import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

ROOT = Path(__file__).resolve().parent
TS = int(time.time())
LOCAL_TAR = ROOT / f"prd448_h5_src_{TS}.tar.gz"
REMOTE_TAR = f"/tmp/prd448_h5_src_{TS}.tar.gz"


def main() -> None:
    # --- Step 0: pack h5-web/src locally ---
    print("=" * 70)
    print("Step 0: tar h5-web/src locally")
    print("=" * 70)
    h5_src = ROOT / "h5-web" / "src"
    if not h5_src.exists():
        print(f"ERROR: {h5_src} not found")
        sys.exit(1)
    with tarfile.open(LOCAL_TAR, "w:gz") as tar:
        tar.add(h5_src, arcname="h5-web/src")
    sz = LOCAL_TAR.stat().st_size
    print(f"local tar: {LOCAL_TAR}  ({sz/1024/1024:.2f} MB)")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=60)

    def run(cmd: str, timeout: int = 1200, show_tail: int = 3000):
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(f"\n$ {cmd[:160]}")
        print(f"[rc={rc}]")
        if out:
            print(out[-show_tail:])
        if err and rc != 0:
            print("ERR:", err[-1500:])
        return rc, out, err

    # --- Step 1: SFTP upload ---
    print("=" * 70)
    print("Step 1: SFTP upload")
    print("=" * 70)
    sftp = ssh.open_sftp()
    sftp.put(str(LOCAL_TAR), REMOTE_TAR)
    sftp.close()
    print(f"uploaded -> {REMOTE_TAR}")

    # --- Step 2: extract & verify ---
    print("=" * 70)
    print("Step 2: extract & verify on server")
    print("=" * 70)
    cmds = [
        f"cd {REMOTE_PROJECT_DIR} && rm -rf .prd448_backup && mkdir -p .prd448_backup",
        f"cd {REMOTE_PROJECT_DIR} && cp -r h5-web/src .prd448_backup/h5_src",
        f"cd {REMOTE_PROJECT_DIR} && tar -xzf {REMOTE_TAR}",
        f"ls {REMOTE_PROJECT_DIR}/h5-web/src/components/ai-chat/AdvisorCapsule/",
        f"grep -c 'PRD-448' {REMOTE_PROJECT_DIR}/h5-web/src/components/ai-chat/AdvisorCapsule/index.tsx",
        f"grep -c \"variant === 'capsule'\" {REMOTE_PROJECT_DIR}/h5-web/src/components/ai-chat/ProfileCard.tsx",
        f"grep -c 'PRD-448' {REMOTE_PROJECT_DIR}/h5-web/src/app/chat/\\[sessionId\\]/page.tsx",
        f"grep -c 'PRD-448' {REMOTE_PROJECT_DIR}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
    ]
    for c in cmds:
        run(c, timeout=120)

    # --- Step 3: rebuild h5-web container only ---
    print("=" * 70)
    print("Step 3: rebuild h5-web container (no-cache)")
    print("=" * 70)
    rc, out, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -80",
        timeout=1500,
    )
    if rc != 0:
        print("h5-web build FAILED, rolling back source ...")
        run(
            f"cd {REMOTE_PROJECT_DIR} && rm -rf h5-web/src && cp -r .prd448_backup/h5_src h5-web/src"
        )
        ssh.close()
        sys.exit(2)

    rc, _, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web",
        timeout=120,
    )
    if rc != 0:
        print("h5-web up failed, abort.")
        ssh.close()
        sys.exit(3)

    run(
        f"docker ps --filter name={DEPLOY_ID}-h5 --format '{{{{.Names}}}}|{{{{.Status}}}}'"
    )

    # --- Step 4: ensure gateway in network ---
    run(
        f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true"
    )

    # --- Step 5: cleanup ---
    run(f"rm -f {REMOTE_TAR}")
    LOCAL_TAR.unlink(missing_ok=True)

    # --- Step 6: smoke test ---
    print("=" * 70)
    print("Step 6: wait 25s & smoke test")
    print("=" * 70)
    time.sleep(25)

    smoke_paths = [
        "/",
        "/login/",
        "/ai-home/",
        "/chat-history/",
    ]
    pass_count = 0
    for p in smoke_paths:
        url = BASE_URL + p
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "PRD448-smoke/1.0"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                code = resp.getcode()
                ok = code == 200
                if ok:
                    pass_count += 1
                print(f"  {url}  -> {code}  {'PASS' if ok else 'FAIL'}")
        except Exception as e:
            print(f"  {url}  -> ERROR: {e}")

    print(f"\n[smoke] {pass_count}/{len(smoke_paths)} PASS")

    ssh.close()
    print("=" * 70)
    print(f"PRD-448 deploy DONE. smoke = {pass_count}/{len(smoke_paths)}")
    print("=" * 70)
    sys.exit(0 if pass_count >= len(smoke_paths) - 1 else 2)


if __name__ == "__main__":
    main()
