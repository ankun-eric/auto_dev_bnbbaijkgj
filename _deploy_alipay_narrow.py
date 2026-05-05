"""[需求 2026-05-05] 支付宝应用私钥校验收窄部署脚本。

执行流程：
  1) SCP 上传本地修改的 3 个文件（rsa_key.py / test_alipay_private_key_format.py / payment-config/page.tsx）
  2) SSH 重建 backend + admin-web 镜像
  3) 重启容器
  4) 在 backend 容器内运行 pytest 校验测试通过
  5) curl 验证 admin / 后端 / h5 主页可达性
"""
from __future__ import annotations

import sys
import time

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# 本地 → 服务器 文件映射
FILES = [
    (
        r"C:\auto_output\bnbbaijkgj\backend\app\utils\rsa_key.py",
        f"{PROJECT_DIR}/backend/app/utils/rsa_key.py",
    ),
    (
        r"C:\auto_output\bnbbaijkgj\backend\tests\test_alipay_private_key_format.py",
        f"{PROJECT_DIR}/backend/tests/test_alipay_private_key_format.py",
    ),
    (
        r"C:\auto_output\bnbbaijkgj\admin-web\src\app\(admin)\payment-config\page.tsx",
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/payment-config/page.tsx",
    ),
]


def run_ssh(client, cmd, timeout=900):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[:8000], flush=True)
    if err.strip():
        print(f"[STDERR] {err.strip()[:4000]}", flush=True)
    print(f"[EXIT {code}]", flush=True)
    return code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=60)
    print("Connected.", flush=True)

    # 1) 上传修改后的文件
    sftp = client.open_sftp()
    for local, remote in FILES:
        print(f"\n--- Upload: {local} -> {remote}", flush=True)
        sftp.put(local, remote)
    sftp.close()

    code, _, _ = run_ssh(client, "docker compose version")
    compose = "docker compose" if code == 0 else "docker-compose"
    cmd_prefix = f"cd {PROJECT_DIR} && {compose} -f docker-compose.prod.yml"

    # 2) 重建 backend (只是 .py，可热重启，但保险起见 rebuild)
    print("\n=== Rebuild backend ===", flush=True)
    run_ssh(client, f"{cmd_prefix} build backend", timeout=900)

    # 3) 重建 admin-web
    print("\n=== Rebuild admin-web ===", flush=True)
    run_ssh(client, f"{cmd_prefix} build admin-web", timeout=900)

    # 4) 启动
    print("\n=== Up -d backend admin-web ===", flush=True)
    run_ssh(client, f"{cmd_prefix} up -d backend admin-web", timeout=300)

    # 5) 等待容器健康
    time.sleep(8)
    run_ssh(client, "docker ps --filter name=" + DEPLOY_ID + " --format '{{.Names}}\\t{{.Status}}'")

    # 6) 容器内跑 pytest
    print("\n=== Run pytest test_alipay_private_key_format ===", flush=True)
    test_cmd = (
        f"docker exec {DEPLOY_ID}-backend "
        "python -m pytest tests/test_alipay_private_key_format.py -v --no-header --tb=short"
    )
    pcode, pout, perr = run_ssh(client, test_cmd, timeout=300)

    # 7) 验证主页可达
    print("\n=== Verify accessibility ===", flush=True)
    run_ssh(
        client,
        f"curl -s -o /dev/null -w 'admin: %{{http_code}}\\n' {BASE_URL}/admin/",
    )
    run_ssh(
        client,
        f"curl -s -o /dev/null -w 'health: %{{http_code}}\\n' {BASE_URL}/api/health",
    )
    run_ssh(
        client,
        f"curl -s -o /dev/null -w 'h5: %{{http_code}}\\n' {BASE_URL}/",
    )

    client.close()
    print("\n=== Deploy done ===", flush=True)
    if pcode != 0:
        print("[WARN] pytest failed, see output above", flush=True)
        sys.exit(1)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
