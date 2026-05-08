"""[Bug-419 2026-05-08] H5 ai-home 整片白屏 + 创建会话 422 修复 部署脚本。

流程：
1. paramiko SFTP 上传：
   - backend/app/schemas/chat.py（ChatSessionCreate 字段优化 + member_id 兼容）
   - backend/app/api/chat.py（路由层 session_type 归一化 + family_member_id 兜底）
   - backend/app/main.py（全局 422 中文化处理器）
   - backend/tests/test_bug419_chat_sessions.py（9 用例 T01-T09）
   - h5-web/src/lib/chat-session.ts（统一 createChatSession 工具）
   - h5-web/src/components/SectionErrorBoundary.tsx（区块级 ErrorBoundary）
   - h5-web/src/app/(ai-chat)/ai-home/page.tsx（核心修复页面）
   - h5-web/src/app/tcm/page.tsx
   - h5-web/src/app/symptom/page.tsx
   - h5-web/src/components/ChatSidebar.tsx
   - h5-web/src/app/(tabs)/ai/page.tsx
2. SSH docker cp backend 文件到容器并 restart backend
3. SSH docker cp 测试文件并跑 pytest（PRD 405/411/414 + Bug410/417 + Bug419）
4. SSH docker compose build h5-web && up -d
5. 远程 smoke 验证 /api/health / /api/chat/sessions（带 token）/ /api/ai-home-config / /
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
    # 后端 schema + API + 全局异常处理器
    ("backend/app/schemas/chat.py",
     f"{PROJECT_DIR}/backend/app/schemas/chat.py"),
    ("backend/app/api/chat.py",
     f"{PROJECT_DIR}/backend/app/api/chat.py"),
    ("backend/app/main.py",
     f"{PROJECT_DIR}/backend/app/main.py"),
    # 后端测试
    ("backend/tests/test_bug419_chat_sessions.py",
     f"{PROJECT_DIR}/backend/tests/test_bug419_chat_sessions.py"),
    # h5-web 工具与组件
    ("h5-web/src/lib/chat-session.ts",
     f"{PROJECT_DIR}/h5-web/src/lib/chat-session.ts"),
    ("h5-web/src/components/SectionErrorBoundary.tsx",
     f"{PROJECT_DIR}/h5-web/src/components/SectionErrorBoundary.tsx"),
    # h5-web 各创建会话入口
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/app/tcm/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/tcm/page.tsx"),
    ("h5-web/src/app/symptom/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/symptom/page.tsx"),
    ("h5-web/src/components/ChatSidebar.tsx",
     f"{PROJECT_DIR}/h5-web/src/components/ChatSidebar.tsx"),
    ("h5-web/src/app/(tabs)/ai/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/(tabs)/ai/page.tsx"),
]

# 后端文件 docker cp 到容器（restart 后生效）
BACKEND_TO_CONTAINER = [
    ("backend/app/schemas/chat.py", "/app/app/schemas/chat.py"),
    ("backend/app/api/chat.py", "/app/app/api/chat.py"),
    ("backend/app/main.py", "/app/app/main.py"),
    ("backend/tests/test_bug419_chat_sessions.py", "/app/tests/test_bug419_chat_sessions.py"),
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
    time.sleep(10)

    # 4. 容器内 pytest 跑 Bug-419 用例 + 关键回归
    print("\n[容器内 pytest - Bug-419]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_bug419_chat_sessions.py "
        f"-x -v --tb=short 2>&1 | tail -120'",
        timeout=900,
    )

    print("\n[容器内 pytest - 关键回归（PRD-405/411/414 + Bug410/417）]")
    run(
        ssh,
        f"docker exec {backend_container} bash -c "
        f"'cd /app && pytest tests/test_ai_home_config.py "
        f"tests/test_ai_home_config_v1.py tests/test_ai_home_config_tab411.py "
        f"tests/test_ai_chat_v11_414.py "
        f"tests/test_bugfix_reschedule_popup_auto_close.py "
        f"-q --tb=line 2>&1 | tail -60'",
        timeout=900,
    )

    # 5. h5-web 重建
    print("\n[h5-web build]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -60",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose up -d h5-web", timeout=120)

    print("\n等待 h5-web 启动...")
    time.sleep(10)

    # 6. smoke
    smoke_urls = [
        "/api/health",
        "/api/ai-home-config",
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
