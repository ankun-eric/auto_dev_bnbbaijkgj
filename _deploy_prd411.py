"""[PRD-411 2026-05-08] AI 对话首页配置 6 Tab 化改造 部署脚本。

1. paramiko SFTP 上传 admin-web/page.tsx + 后端测试文件
2. SSH docker cp 测试文件到 backend 容器
3. 容器内 pytest 跑 PRD-405 + PRD-411 全部测试
4. SSH docker compose build admin-web && up -d
5. 远程 smoke 验证 admin/ai-home-config/ 可达
"""
from __future__ import annotations

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

FILES = [
    # admin-web 改造（核心）
    (
        "admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx",
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx",
    ),
    # 后端 PRD-411 测试
    (
        "backend/tests/test_ai_home_config_tab411.py",
        f"{PROJECT_DIR}/backend/tests/test_ai_home_config_tab411.py",
    ),
]

BACKEND_TEST_TO_CONTAINER = [
    ("backend/tests/test_ai_home_config_tab411.py", "/app/tests/test_ai_home_config_tab411.py"),
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
    for local, remote in FILES:
        local_path = Path(local)
        if not local_path.exists():
            print(f"[skip 不存在] {local}")
            continue
        remote_dir = "/".join(remote.split("/")[:-1])
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            run(ssh, f"mkdir -p '{remote_dir}'")
        print(f"\n[上传] {local} → {remote}")
        sftp.put(str(local_path), remote)

    # 2. 后端测试文件 docker cp 到容器（不重启 backend）
    backend_container = f"{DEPLOY_ID}-backend"
    for local, container_path in BACKEND_TEST_TO_CONTAINER:
        host_path = f"{PROJECT_DIR}/{local}"
        run(ssh, f"docker cp '{host_path}' '{backend_container}:{container_path}'")

    # 3. 容器内 pytest 跑全部 ai_home_config 测试（v0/v1/411）
    print("\n[容器内 pytest]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_ai_home_config.py tests/test_ai_home_config_v1.py tests/test_ai_home_config_tab411.py -x -q --tb=short 2>&1 | tail -120'",
        timeout=900,
    )

    # 4. admin-web docker compose build + up
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build admin-web && docker compose up -d admin-web",
        timeout=1500,
    )

    # 等待 admin 启动
    print("\n等待 admin-web 启动...")
    time.sleep(8)

    # 5. smoke
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
