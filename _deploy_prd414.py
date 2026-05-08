"""[PRD-414 v1.1 2026-05-08] AI 对话页优化 部署脚本。

1. paramiko SFTP 上传：
   - backend/app/schemas/ai_home_config.py（新增 ai_chat schema）
   - backend/app/api/ai_home_config.py（新增 ai_chat 模块校验）
   - backend/tests/test_ai_chat_v11_414.py（新增 8 测试用例）
   - admin-web 配置页（新增 AI 对话页配置卡片）
   - h5-web chat 页（注入 ai_chat 配置 + AI 头像 + 档案行 + 回到最新按钮）
2. SSH docker cp backend 文件到容器并 restart backend
3. SSH docker cp 测试文件并跑 pytest（PRD-405 v0+v1+PRD-411+PRD-414 全部）
4. SSH docker compose build admin-web && build h5-web && up -d
5. 远程 smoke 验证
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
    # 后端 schema + API
    ("backend/app/schemas/ai_home_config.py",
     f"{PROJECT_DIR}/backend/app/schemas/ai_home_config.py"),
    ("backend/app/api/ai_home_config.py",
     f"{PROJECT_DIR}/backend/app/api/ai_home_config.py"),
    # 后端测试
    ("backend/tests/test_ai_chat_v11_414.py",
     f"{PROJECT_DIR}/backend/tests/test_ai_chat_v11_414.py"),
    # admin-web
    ("admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx",
     f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx"),
    # h5-web chat 页
    ("h5-web/src/app/chat/[sessionId]/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/chat/[sessionId]/page.tsx"),
]

# 后端文件 docker cp 到容器（restart 后生效）
BACKEND_TO_CONTAINER = [
    ("backend/app/schemas/ai_home_config.py", "/app/app/schemas/ai_home_config.py"),
    ("backend/app/api/ai_home_config.py", "/app/app/api/ai_home_config.py"),
    ("backend/tests/test_ai_chat_v11_414.py", "/app/tests/test_ai_chat_v11_414.py"),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 1200) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:200]}")
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

    backend_container = f"{DEPLOY_ID}-backend"

    # 2. 后端文件 docker cp 到容器
    for local, container_path in BACKEND_TO_CONTAINER:
        host_path = f"{PROJECT_DIR}/{local}"
        run(ssh, f"docker cp '{host_path}' '{backend_container}:{container_path}'")

    # 3. restart backend
    run(ssh, f"docker restart {backend_container}", timeout=120)
    print("等待 backend 启动...")
    time.sleep(8)

    # 4. 容器内 pytest 跑全部 ai_home_config 相关测试
    print("\n[容器内 pytest - PRD-414 v1.1 ai_chat]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_ai_home_config.py tests/test_ai_home_config_v1.py "
        f"tests/test_ai_home_config_tab411.py tests/test_ai_chat_v11_414.py "
        f"-x -q --tb=short 2>&1 | tail -150'",
        timeout=900,
    )

    # 5. admin-web 重建
    print("\n[admin-web build]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build admin-web 2>&1 | tail -50",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose up -d admin-web", timeout=120)

    # 6. h5-web 重建（chat 页改动）
    print("\n[h5-web build]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -50",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose up -d h5-web", timeout=120)

    print("\n等待容器启动...")
    time.sleep(10)

    # 7. smoke
    smoke_urls = [
        "/api/health",
        "/api/ai-home-config",
        "/admin/home-settings/ai-home-config/",
        "/",
    ]
    print("\n[Smoke]")
    for u in smoke_urls:
        run(ssh, f"curl -s -o /dev/null -w '{u}=%{{http_code}}\\n' '{BASE_URL}{u}'")

    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
