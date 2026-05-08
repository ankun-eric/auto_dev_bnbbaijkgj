"""[PRD-425 2026-05-08] AI 对话首页顶栏改造部署脚本。

变更：
1. 后端：新增 backend/app/api/notifications_unified.py 与 main.py 注册
2. 后端：新增测试 backend/tests/test_prd425_unified_unread.py
3. H5：改造 ai-home/page.tsx，新顶栏强制显示 + 未读徽标
4. 小程序：chat/index.{js,wxml,wxss} 顶栏标题与未读徽标
5. Flutter：ai_home_screen.dart 标题与未读徽标
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
    # 后端
    (
        "backend/app/api/notifications_unified.py",
        f"{PROJECT_DIR}/backend/app/api/notifications_unified.py",
    ),
    (
        "backend/app/main.py",
        f"{PROJECT_DIR}/backend/app/main.py",
    ),
    (
        "backend/tests/test_prd425_unified_unread.py",
        f"{PROJECT_DIR}/backend/tests/test_prd425_unified_unread.py",
    ),
    # H5
    (
        "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    ),
    # 小程序
    (
        "miniprogram/pages/chat/index.js",
        f"{PROJECT_DIR}/miniprogram/pages/chat/index.js",
    ),
    (
        "miniprogram/pages/chat/index.wxml",
        f"{PROJECT_DIR}/miniprogram/pages/chat/index.wxml",
    ),
    (
        "miniprogram/pages/chat/index.wxss",
        f"{PROJECT_DIR}/miniprogram/pages/chat/index.wxss",
    ),
    # Flutter
    (
        "flutter_app/lib/screens/ai/ai_home_screen.dart",
        f"{PROJECT_DIR}/flutter_app/lib/screens/ai/ai_home_screen.dart",
    ),
]

# 后端测试文件 docker cp 到容器
BACKEND_TO_CONTAINER = [
    (
        "backend/app/api/notifications_unified.py",
        "/app/app/api/notifications_unified.py",
    ),
    (
        "backend/app/main.py",
        "/app/app/main.py",
    ),
    (
        "backend/tests/test_prd425_unified_unread.py",
        "/app/tests/test_prd425_unified_unread.py",
    ),
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
    h5_container = f"{DEPLOY_ID}-frontend"

    # 2. 后端 docker cp 业务代码 + 测试到容器
    for local, container_path in BACKEND_TO_CONTAINER:
        host_path = f"{PROJECT_DIR}/{local}"
        run(ssh, f"docker cp '{host_path}' '{backend_container}:{container_path}'")

    # 3. 重启 backend 让新接口生效
    print("\n[重启 backend 容器]")
    run(ssh, f"docker restart {backend_container}", timeout=120)
    time.sleep(8)

    # 4. 容器内 pytest 跑 PRD-425 用例
    print("\n[容器内 pytest - PRD-425]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_prd425_unified_unread.py "
        f"-v --tb=short 2>&1 | tail -80'",
        timeout=900,
    )

    # 5. 关键回归
    print("\n[容器内 pytest - 关键回归（Bug-419 + ai-home v1）]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_bug419_chat_sessions.py "
        f"tests/test_ai_home_config.py "
        f"-q --tb=line 2>&1 | tail -40'",
        timeout=900,
    )

    # 6. h5-web 重建
    print("\n[h5-web build]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -60",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose up -d h5-web", timeout=120)

    print("\n等待 h5-web 启动...")
    time.sleep(12)

    # 7. smoke
    smoke_urls = [
        "/api/health",
        "/api/v1/notifications/unread-count",  # 新接口（401/403 也算可达）
        "/",
        "/ai-home",
    ]
    print("\n[Smoke]")
    for u in smoke_urls:
        run(ssh, f"curl -s -o /dev/null -w '{u}=%{{http_code}}\\n' '{BASE_URL}{u}'")

    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
