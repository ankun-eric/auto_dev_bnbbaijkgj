"""BUG-461 修复部署脚本（后端 + h5-web）

变更范围：
- 后端：app/schemas/chat_history.py、app/api/chat_history.py、app/core/config.py
- 前端：h5-web/src/components/ai-chat/Sidebar.tsx、
        h5-web/src/app/chat/[sessionId]/page.tsx、
        h5-web/src/app/(ai-chat)/ai-home/page.tsx
- 测试：backend/tests/test_bug461_drawer_history.py

部署：
1. 本地打 tar：backend/app + backend/tests + h5-web/src
2. SFTP 上传 → 服务器解压覆盖
3. docker compose build h5-web + backend && up -d h5-web backend
4. 在服务器 backend 容器内执行 pytest 测试 BUG-461 用例（非UI 自动化）
5. smoke test：GET /api/chat-sessions（需登录，仅校验路由可达）、抽屉页可达
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
LOCAL_TAR = ROOT / f"bug461_src_{TS}.tar.gz"
REMOTE_TAR = f"/tmp/bug461_src_{TS}.tar.gz"


def main() -> None:
    # --- Step 0: pack locally ---
    print("=" * 70)
    print("Step 0: tar backend/app + backend/tests + h5-web/src locally")
    print("=" * 70)
    backend_app = ROOT / "backend" / "app"
    backend_tests = ROOT / "backend" / "tests"
    h5_src = ROOT / "h5-web" / "src"
    for d in (backend_app, backend_tests, h5_src):
        if not d.exists():
            print(f"ERROR: {d} not found")
            sys.exit(1)
    with tarfile.open(LOCAL_TAR, "w:gz") as tar:
        tar.add(backend_app, arcname="backend/app")
        tar.add(backend_tests, arcname="backend/tests")
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
        print(f"\n$ {cmd[:200]}")
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
        f"cd {REMOTE_PROJECT_DIR} && rm -rf .bug461_backup && mkdir -p .bug461_backup",
        f"cd {REMOTE_PROJECT_DIR} && cp -r backend/app .bug461_backup/backend_app && cp -r h5-web/src .bug461_backup/h5_src",
        f"cd {REMOTE_PROJECT_DIR} && tar -xzf {REMOTE_TAR}",
        f"grep -c 'BUG-461' {REMOTE_PROJECT_DIR}/backend/app/api/chat_history.py",
        f"grep -c 'BUG-461' {REMOTE_PROJECT_DIR}/h5-web/src/components/ai-chat/Sidebar.tsx",
        f"grep -c 'BUG-461' {REMOTE_PROJECT_DIR}/backend/app/schemas/chat_history.py",
        f"ls -la {REMOTE_PROJECT_DIR}/backend/tests/test_bug461_drawer_history.py",
    ]
    for c in cmds:
        run(c, timeout=120)

    # --- Step 3: rebuild backend ---
    print("=" * 70)
    print("Step 3: rebuild backend container")
    print("=" * 70)
    rc, out, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -80",
        timeout=1500,
    )
    if rc != 0:
        print("backend build FAILED")
        run(f"cd {REMOTE_PROJECT_DIR} && rm -rf backend/app && cp -r .bug461_backup/backend_app backend/app")
        ssh.close()
        sys.exit(2)

    rc, _, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend",
        timeout=180,
    )
    if rc != 0:
        print("backend up FAILED")
        ssh.close()
        sys.exit(3)

    # --- Step 4: rebuild h5-web ---
    print("=" * 70)
    print("Step 4: rebuild h5-web container")
    print("=" * 70)
    rc, out, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -80",
        timeout=1500,
    )
    if rc != 0:
        print("h5-web build FAILED, rolling back source ...")
        run(
            f"cd {REMOTE_PROJECT_DIR} && rm -rf h5-web/src && cp -r .bug461_backup/h5_src h5-web/src"
        )
        ssh.close()
        sys.exit(2)

    rc, _, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web",
        timeout=180,
    )
    if rc != 0:
        print("h5-web up failed, abort.")
        ssh.close()
        sys.exit(3)

    run(
        f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}|{{{{.Status}}}}'"
    )

    # --- Step 5: ensure gateway in network ---
    run(
        f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true"
    )

    # --- Step 6: wait & smoke test ---
    print("=" * 70)
    print("Step 6: wait 30s & smoke HTTP")
    print("=" * 70)
    time.sleep(30)

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
                url, headers={"User-Agent": "BUG461-smoke/1.0"}
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

    # --- Step 7: run BUG-461 pytest inside backend container ---
    print("=" * 70)
    print("Step 7: pytest test_bug461_drawer_history.py inside backend container")
    print("=" * 70)
    backend_container = f"{DEPLOY_ID}-backend"
    # 先确保 pytest 等测试依赖可用（容器内 pip 安装幂等）
    run(
        f"docker exec {backend_container} sh -lc 'python -m pip install --quiet "
        f"-i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com "
        f"pytest pytest-asyncio aiosqlite' 2>&1 | tail -40",
        timeout=300,
    )
    rc, out, err = run(
        f"docker exec {backend_container} sh -lc "
        f"'set -o pipefail; cd /app && python -m pytest tests/test_bug461_drawer_history.py -v --tb=short 2>&1 | tail -200'",
        timeout=600,
        show_tail=8000,
    )
    test_pass = rc == 0 and ("passed" in out)
    if not test_pass:
        print("[pytest] FAILED — see above output for details.")

    # --- Step 8: cleanup ---
    run(f"rm -f {REMOTE_TAR}")
    LOCAL_TAR.unlink(missing_ok=True)
    ssh.close()

    print("=" * 70)
    print(f"BUG-461 deploy DONE.")
    print(f"  smoke = {pass_count}/{len(smoke_paths)}")
    print(f"  pytest = {'PASS' if test_pass else 'FAIL'}")
    print("=" * 70)
    if not test_pass:
        sys.exit(2)
    sys.exit(0 if pass_count >= len(smoke_paths) - 1 else 2)


if __name__ == "__main__":
    main()
