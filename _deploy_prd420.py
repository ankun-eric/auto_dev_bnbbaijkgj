"""[PRD-420 2026-05-08] AI 对话模式 - 咨询对象选择器 部署脚本。

PRD F7 明确：本次需求"无需任何后端接口新增或改造"。所以本部署脚本核心：
1. 上传新建/修改的前端代码（h5-web 2 文件）
2. 上传后端契约回归测试（backend/tests/test_prd420_consult_target_picker.py）
3. docker cp 测试文件到容器并跑 pytest（regression：确保 family/chat 接口契约稳定）
4. docker compose build h5-web && up -d
5. 远程 smoke /api/health, /api/family/members, /api/relation-types, /, /ai-home

小程序与 Flutter 端的源码已修改但本脚本不涉及打包（小程序需在微信开发者工具上传体验版；
Flutter 在阶段 4 单独打 APK + IPA）。
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
    # h5-web 新组件 + ai-home 集成改造
    (
        "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
        f"{PROJECT_DIR}/h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
    ),
    (
        "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    ),
    # 后端测试（PRD-420 行为契约回归）
    (
        "backend/tests/test_prd420_consult_target_picker.py",
        f"{PROJECT_DIR}/backend/tests/test_prd420_consult_target_picker.py",
    ),
]

# 后端测试文件 docker cp 到容器
BACKEND_TO_CONTAINER = [
    (
        "backend/tests/test_prd420_consult_target_picker.py",
        "/app/tests/test_prd420_consult_target_picker.py",
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

    # 2. 后端测试文件 docker cp 到容器（仅测试文件，无业务代码改动）
    for local, container_path in BACKEND_TO_CONTAINER:
        host_path = f"{PROJECT_DIR}/{local}"
        run(ssh, f"docker cp '{host_path}' '{backend_container}:{container_path}'")

    # 3. 容器内 pytest 跑 PRD-420 用例 + 关键回归
    print("\n[容器内 pytest - PRD-420]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_prd420_consult_target_picker.py "
        f"-v --tb=short 2>&1 | tail -60'",
        timeout=900,
    )

    print("\n[容器内 pytest - 关键回归（Bug-419 创建会话 + ai-home 配置）]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_bug419_chat_sessions.py "
        f"tests/test_ai_home_config.py "
        f"-q --tb=line 2>&1 | tail -60'",
        timeout=900,
    )

    # 4. h5-web 重建
    print("\n[h5-web build]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -60",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose up -d h5-web", timeout=120)

    print("\n等待 h5-web 启动...")
    time.sleep(10)

    # 5. smoke
    smoke_urls = [
        "/api/health",
        "/api/relation-types",
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
