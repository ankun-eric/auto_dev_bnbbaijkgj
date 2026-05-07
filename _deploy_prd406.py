"""[PRD-405 v1.0 / cursor_prompt_406] 部署脚本：

1. paramiko SFTP 上传后端 / admin-web / h5-web 改动文件到服务器
2. SSH 执行 docker cp + docker restart backend、docker compose build + up admin-web 与 h5-web
3. 容器内 pytest 跑 PRD-405 v1.0 测试
4. 远程 smoke 验证
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

# 本地 → 容器 映射
FILES = [
    # 后端
    ("backend/app/api/ai_home_config.py", f"{PROJECT_DIR}/backend/app/api/ai_home_config.py", "backend", "/app/app/api/ai_home_config.py"),
    ("backend/app/schemas/ai_home_config.py", f"{PROJECT_DIR}/backend/app/schemas/ai_home_config.py", "backend", "/app/app/schemas/ai_home_config.py"),
    ("backend/tests/test_ai_home_config_v1.py", f"{PROJECT_DIR}/backend/tests/test_ai_home_config_v1.py", "backend", "/app/tests/test_ai_home_config_v1.py"),
    # admin-web
    ("admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx", None, None),
    # h5-web
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx", f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx", None, None),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 1200) -> tuple[int, str, str]:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err:
        print("STDERR:", err[-2000:])
    print(f"<<< exit={code}")
    return code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, PORT, USER, PASSWORD, timeout=30)

    sftp = ssh.open_sftp()

    # 1. 上传文件
    for local, remote, container_name, container_path in FILES:
        local_path = Path(local)
        if not local_path.exists():
            print(f"[skip 不存在] {local}")
            continue
        # 确保远程目录存在
        remote_dir = "/".join(remote.split("/")[:-1])
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            run(ssh, f"mkdir -p '{remote_dir}'")
        print(f"\n[上传] {local} → {remote}")
        sftp.put(str(local_path), remote)

    # 2. 后端：docker cp + restart
    backend_files = [
        ("backend/app/api/ai_home_config.py", "/app/app/api/ai_home_config.py"),
        ("backend/app/schemas/ai_home_config.py", "/app/app/schemas/ai_home_config.py"),
        ("backend/tests/test_ai_home_config_v1.py", "/app/tests/test_ai_home_config_v1.py"),
    ]
    backend_container = f"{DEPLOY_ID}-backend"
    for local, container_path in backend_files:
        host_path = f"{PROJECT_DIR}/{local}"
        run(ssh, f"docker cp '{host_path}' '{backend_container}:{container_path}'")
    run(ssh, f"docker restart {backend_container}")

    # 等待 backend 就绪
    print("\n等待 backend 启动...")
    for i in range(20):
        time.sleep(3)
        code, _, _ = run(ssh, f"curl -sf {BASE_URL}/api/health -o /dev/null && echo ok || echo waiting")
        if code == 0:
            break

    # 3. 容器内跑测试
    print("\n[容器内 pytest]")
    code, out, err = run(
        ssh,
        f"docker exec {backend_container} bash -c 'cd /app && pytest tests/test_ai_home_config.py tests/test_ai_home_config_v1.py -x -q --tb=short 2>&1 | tail -80'",
        timeout=600,
    )

    # 4. admin-web docker compose build + up
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build admin-web && docker compose up -d admin-web",
        timeout=900,
    )

    # 5. h5-web docker compose build + up
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build h5-web && docker compose up -d h5-web",
        timeout=900,
    )

    # 等待 frontend 就绪
    print("\n等待 admin/h5 启动...")
    time.sleep(10)

    # 6. smoke
    smoke_urls = [
        "/api/health",
        "/api/ai-home-config",
        "/admin/home-settings/ai-home-config/",
        "/admin/home-settings/ai-home-config/logs/",
        "/",
    ]
    print("\n[Smoke]")
    for u in smoke_urls:
        run(ssh, f"curl -s -o /dev/null -w '{u}=%{{http_code}}\\n' {BASE_URL}{u}")

    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
