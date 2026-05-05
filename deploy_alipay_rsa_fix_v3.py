"""[Bug 修复 2026-05-05 v3] 补充：重建 admin-web + 服务器侧自动化测试。"""
from __future__ import annotations

import sys
import time

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run_ssh(client, cmd, timeout=900):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[:6000], flush=True)
    if err.strip():
        print(f"[STDERR] {err.strip()[:3000]}", flush=True)
    print(f"[EXIT {code}]", flush=True)
    return code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=60)
    print("Connected.", flush=True)

    code, _, _ = run_ssh(client, "docker compose version")
    compose = "docker compose" if code == 0 else "docker-compose"
    cmd_prefix = f"cd {PROJECT_DIR} && {compose} -f docker-compose.prod.yml"

    # 列出所有 services
    print("\n=== Services list ===", flush=True)
    run_ssh(client, f"{cmd_prefix} config --services")

    # admin-web 重建（前端 .tsx 改动）
    print("\n=== Rebuild admin-web ===", flush=True)
    code, _, _ = run_ssh(client, f"{cmd_prefix} build admin-web", timeout=900)

    # 启动
    print("\n=== Up -d admin-web ===", flush=True)
    run_ssh(client, f"{cmd_prefix} up -d admin-web", timeout=120)

    # 等容器就绪
    time.sleep(10)
    run_ssh(client, f"{cmd_prefix} ps")

    # gateway reconnect/reload
    run_ssh(client, f"docker network connect {DEPLOY_ID}-network gateway 2>/dev/null || true")
    run_ssh(client, "docker exec gateway nginx -s reload 2>/dev/null || true")

    # 验证 admin-web 路径可达
    print("\n=== Verify admin-web reachability ===", flush=True)
    base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    run_ssh(client, f"curl -sk -o /dev/null -w 'admin %{{http_code}}\\n' {base}/admin/login")
    run_ssh(client, f"curl -sk -o /dev/null -w 'h5 %{{http_code}}\\n' {base}/")
    run_ssh(client, f"curl -sk -o /dev/null -w 'api %{{http_code}}\\n' {base}/api/health")
    run_ssh(client, f"curl -sk -o /dev/null -w 'docs %{{http_code}}\\n' {base}/docs")

    # 在 backend 容器中安装 pytest 并运行测试
    print("\n=== Install pytest & run targeted tests ===", flush=True)
    backend_ct = f"{DEPLOY_ID}-backend"
    run_ssh(client,
        f"docker exec {backend_ct} sh -lc "
        f"'pip install -q pytest pytest-asyncio httpx aiosqlite "
        f"-i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com'",
        timeout=240)

    test_files = " ".join([
        "tests/test_alipay_private_key_format.py",
    ])
    print("\n=== pytest: rsa_key 单元测试（无需DB） ===", flush=True)
    code, out, _ = run_ssh(client,
        f"docker exec -e PYTHONPATH=/app {backend_ct} sh -lc "
        f"'cd /app && python -m pytest {test_files} -v --tb=short 2>&1 | tail -60'",
        timeout=300)

    client.close()
    print("\n=== Done ===", flush=True)
    sys.exit(0 if code == 0 else 2)


if __name__ == "__main__":
    main()
