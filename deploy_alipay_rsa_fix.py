"""[Bug 修复 2026-05-05] 部署支付宝私钥 RSA 格式修复。

变更范围：
  - backend/app/utils/rsa_key.py（新增）
  - backend/app/api/payment_config.py（改）
  - backend/app/services/alipay_service.py（改）
  - admin-web/src/app/(admin)/payment-config/page.tsx（改）
  - backend/tests/*.py（新增/改）

部署策略：
  1. SSH 登录服务器，git pull 拉最新代码
  2. 重建并重启 backend 容器（Python 代码改动 → docker compose up -d --build backend）
  3. 重建并重启 frontend 容器（.tsx 改动 → docker compose up -d --build frontend）
  4. 等待健康检查通过
  5. 重连 gateway 网络 + reload nginx
  6. 在 backend 容器中跑非 UI 自动化测试（pytest 选定测试文件）
"""
from __future__ import annotations

import sys
import time

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def run_ssh(client, cmd, timeout=600, capture=True):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip(), flush=True)
    if err.strip():
        print(f"[STDERR] {err.strip()}", flush=True)
    print(f"[EXIT {code}]", flush=True)
    return code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {SSH_HOST}...", flush=True)
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=60)
    print("Connected.", flush=True)

    # Step 1: pull
    print("\n=== STEP 1: Pull latest code ===", flush=True)
    code, _, _ = run_ssh(client,
        f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master "
        f"&& git clean -fd -- backend admin-web && git log -1 --oneline")
    if code != 0:
        run_ssh(client,
            f"cd {PROJECT_DIR} && git remote set-url origin "
            f"https://ankun-eric:{GH_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git")
        code, _, _ = run_ssh(client,
            f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master "
            f"&& git log -1 --oneline")
        if code != 0:
            print("FATAL: git pull failed", flush=True)
            sys.exit(1)

    # Step 2: docker compose
    code, _, _ = run_ssh(client, "docker compose version")
    compose = "docker compose" if code == 0 else "docker-compose"
    cmd_prefix = f"cd {PROJECT_DIR} && {compose} -f docker-compose.prod.yml"

    print("\n=== STEP 2: Rebuild backend (no-cache for clean state) ===", flush=True)
    run_ssh(client, f"{cmd_prefix} build --no-cache backend", timeout=600)

    print("\n=== STEP 3: Rebuild frontend ===", flush=True)
    run_ssh(client, f"{cmd_prefix} build --no-cache frontend", timeout=900)

    print("\n=== STEP 4: docker compose up -d ===", flush=True)
    run_ssh(client, f"{cmd_prefix} up -d", timeout=180)

    # Step 4: wait
    print("\n=== STEP 5: Wait for health ===", flush=True)
    for i in range(24):
        time.sleep(5)
        code, out, _ = run_ssh(client, f"{cmd_prefix} ps")
        if "unhealthy" not in out and ("Up" in out or "healthy" in out) and i >= 4:
            break
        print(f"... waiting {(i+1)*5}s", flush=True)

    # Step 5: reconnect gateway
    print("\n=== STEP 6: gateway reconnect & reload ===", flush=True)
    run_ssh(client, f"docker network connect {DEPLOY_ID}-network gateway 2>/dev/null || true")
    run_ssh(client, "docker exec gateway nginx -s reload 2>/dev/null || true")

    # Step 6: container status
    print("\n=== STEP 7: Final status ===", flush=True)
    run_ssh(client, f"{cmd_prefix} ps")

    # Step 7: run targeted backend tests inside container
    print("\n=== STEP 8: Run targeted pytest inside backend container ===", flush=True)
    backend_container = f"{DEPLOY_ID}-backend"
    test_files = " ".join([
        "tests/test_alipay_private_key_format.py",
        "tests/test_payment_config_alipay_save_validation.py",
        "tests/test_payment_config_test_connection_error_message.py",
        "tests/test_payment_config_first_time_secret.py",
    ])
    code, out, err = run_ssh(client,
        f"docker exec {backend_container} sh -lc "
        f"'cd /app && python -m pytest {test_files} -x --tb=short 2>&1 | tail -120'",
        timeout=600)

    client.close()
    print("\n=== Deployment complete ===", flush=True)
    sys.exit(0 if code == 0 else 2)


if __name__ == "__main__":
    main()
