"""[Bug 修复 2026-05-05 v2] 通过 SCP 直传变更文件到服务器，绕开 GitHub 网络。"""
from __future__ import annotations

import os
import sys
import time

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# 本次变更文件清单（本地路径，相对工作目录）
CHANGED_FILES = [
    "backend/app/utils/rsa_key.py",
    "backend/app/api/payment_config.py",
    "backend/app/services/alipay_service.py",
    "backend/tests/test_alipay_private_key_format.py",
    "backend/tests/test_payment_config_alipay_save_validation.py",
    "backend/tests/test_payment_config_test_connection_error_message.py",
    "backend/tests/test_payment_config_first_time_secret.py",
    "admin-web/src/app/(admin)/payment-config/page.tsx",
]


def run_ssh(client, cmd, timeout=600):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[:4000], flush=True)
    if err.strip():
        print(f"[STDERR] {err.strip()[:2000]}", flush=True)
    print(f"[EXIT {code}]", flush=True)
    return code, out, err


def main():
    workdir = os.path.dirname(os.path.abspath(__file__))

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {SSH_HOST}...", flush=True)
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=60)
    print("Connected.", flush=True)

    # Step 1: SCP 直传变更文件
    print("\n=== STEP 1: SCP changed files ===", flush=True)
    sftp = client.open_sftp()
    for rel in CHANGED_FILES:
        local = os.path.join(workdir, rel.replace("/", os.sep))
        remote = f"{PROJECT_DIR}/{rel}"
        if not os.path.isfile(local):
            print(f"[SKIP] local file not found: {local}", flush=True)
            continue
        # 确保远程目录存在
        remote_dir = "/".join(remote.split("/")[:-1])
        run_ssh(client, f"mkdir -p '{remote_dir}'")
        sftp.put(local, remote)
        print(f"  uploaded: {rel}", flush=True)
    sftp.close()

    # Step 2: 选择 docker compose
    code, _, _ = run_ssh(client, "docker compose version")
    compose = "docker compose" if code == 0 else "docker-compose"
    cmd_prefix = f"cd {PROJECT_DIR} && {compose} -f docker-compose.prod.yml"

    # Step 3: 重启 backend (Python 代码改动 → 直接 restart 即可，volume 挂载或镜像内代码？)
    # 先检查 backend Dockerfile 是否将 backend 代码 COPY 进镜像（典型情况）
    print("\n=== STEP 2: Inspect backend container layout ===", flush=True)
    run_ssh(client, f"docker exec {DEPLOY_ID}-backend ls /app/app/utils/ 2>&1 | head -10")

    # 假定代码 COPY 进镜像 → 必须 rebuild backend，否则容器内仍是旧代码
    print("\n=== STEP 3: Rebuild backend ===", flush=True)
    run_ssh(client, f"{cmd_prefix} build backend", timeout=600)

    print("\n=== STEP 4: Rebuild frontend (admin-web) ===", flush=True)
    run_ssh(client, f"{cmd_prefix} build frontend", timeout=900)

    print("\n=== STEP 5: docker compose up -d ===", flush=True)
    run_ssh(client, f"{cmd_prefix} up -d", timeout=180)

    # Step 4: wait
    print("\n=== STEP 6: Wait for health ===", flush=True)
    for i in range(18):
        time.sleep(5)
        code, out, _ = run_ssh(client, f"{cmd_prefix} ps")
        if "unhealthy" not in out and "Up" in out and i >= 3:
            break
        print(f"... waiting {(i+1)*5}s", flush=True)

    # Step 5: gateway
    print("\n=== STEP 7: gateway reconnect & reload ===", flush=True)
    run_ssh(client, f"docker network connect {DEPLOY_ID}-network gateway 2>/dev/null || true")
    run_ssh(client, "docker exec gateway nginx -s reload 2>/dev/null || true")

    # Step 6: 验证关键文件已生效
    print("\n=== STEP 8: Verify rsa_key.py inside backend container ===", flush=True)
    run_ssh(client, f"docker exec {DEPLOY_ID}-backend ls -la /app/app/utils/rsa_key.py")
    run_ssh(client, f"docker exec {DEPLOY_ID}-backend python -c "
        f"\"from app.utils.rsa_key import normalize_rsa_private_key, USER_FRIENDLY_ERROR; "
        f"print('rsa_key OK:', USER_FRIENDLY_ERROR[:30])\"")

    # Step 7: 跑非UI自动化测试
    print("\n=== STEP 9: Run pytest inside backend container ===", flush=True)
    backend_container = f"{DEPLOY_ID}-backend"
    test_files = " ".join([
        "tests/test_alipay_private_key_format.py",
        "tests/test_payment_config_alipay_save_validation.py",
        "tests/test_payment_config_test_connection_error_message.py",
        "tests/test_payment_config_first_time_secret.py",
    ])
    code, out, err = run_ssh(client,
        f"docker exec {backend_container} sh -lc "
        f"'cd /app && python -m pytest {test_files} --tb=short 2>&1 | tail -80'",
        timeout=600)

    client.close()
    print("\n=== Deployment complete ===", flush=True)
    sys.exit(0 if code == 0 else 2)


if __name__ == "__main__":
    main()
