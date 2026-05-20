"""[BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1 2026-05-21]
部署修复脚本：
1. 上传修改后的后端/H5/admin/小程序/Flutter 代码文件
2. docker compose build/up backend + h5-web + admin-web
3. 等待后端启动，检查迁移日志
4. 探活验证主要 URL
"""

from __future__ import annotations

import subprocess
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
DEPLOY_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

LOCAL_FILES = [
    # backend
    ("backend/app/schemas/ai_home_config.py", f"{DEPLOY_DIR}/backend/app/schemas/ai_home_config.py"),
    ("backend/app/main.py", f"{DEPLOY_DIR}/backend/app/main.py"),
    (
        "backend/app/services/prd_ai_home_archive_path_fix_v1_migration.py",
        f"{DEPLOY_DIR}/backend/app/services/prd_ai_home_archive_path_fix_v1_migration.py",
    ),
    ("backend/tests/test_ai_home_config_v1.py", f"{DEPLOY_DIR}/backend/tests/test_ai_home_config_v1.py"),
    ("backend/tests/test_ai_home_config_tab411.py", f"{DEPLOY_DIR}/backend/tests/test_ai_home_config_tab411.py"),
    # h5
    (
        "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    ),
    # admin
    (
        "admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx",
        f"{DEPLOY_DIR}/admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx",
    ),
    # flutter
    (
        "flutter_app/lib/screens/ai/chat_screen.dart",
        f"{DEPLOY_DIR}/flutter_app/lib/screens/ai/chat_screen.dart",
    ),
    # miniprogram
    (
        "miniprogram/components/profile-card/index.js",
        f"{DEPLOY_DIR}/miniprogram/components/profile-card/index.js",
    ),
]


def sh(cmd: str, *, check: bool = True, timeout: int = 600) -> str:
    print(f"$ {cmd}")
    proc = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out)
    if check and proc.returncode != 0:
        raise SystemExit(f"命令失败: {cmd}\n{out}")
    return out


def ssh(cmd: str, *, timeout: int = 1200, check: bool = True) -> str:
    quoted = cmd.replace('"', '\\"')
    full = (
        f'ssh -o StrictHostKeyChecking=no -o BatchMode=no '
        f"{USER}@{HOST} \"{quoted}\""
    )
    return sh(full, timeout=timeout, check=check)


def scp_one(local: str, remote: str) -> None:
    parent = remote.rsplit("/", 1)[0]
    ssh(f"mkdir -p '{parent}'")
    full = (
        f'scp -o StrictHostKeyChecking=no '
        f'"{local}" "{USER}@{HOST}:{remote}"'
    )
    sh(full)


def main() -> int:
    print("=" * 60)
    print("[BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1] 部署开始")
    print("=" * 60)

    print("\n--- 步骤 1：上传变更文件 ---")
    for local, remote in LOCAL_FILES:
        scp_one(local, remote)

    print("\n--- 步骤 2：重建 backend / h5-web / admin-web ---")
    ssh(
        f"cd {DEPLOY_DIR} && docker compose build backend h5-web admin-web 2>&1 | tail -100",
        timeout=1800,
    )
    ssh(
        f"cd {DEPLOY_DIR} && docker compose up -d backend h5-web admin-web 2>&1 | tail -30",
        timeout=900,
    )

    print("\n--- 步骤 3：等待后端启动（35s） ---")
    time.sleep(35)

    print("\n--- 步骤 4：检查后端迁移日志 ---")
    log = ssh(
        f"docker logs --tail 400 {PROJECT_ID}-backend 2>&1 | "
        f"grep -E 'ai_home_archive_path_fix_v1' || true",
        check=False,
    )
    print(f"迁移日志摘要：\n{log}")

    print("\n--- 步骤 5：探活检查 ---")
    sh(
        f"curl -sS -o NUL -w 'health %{{http_code}}\\n' {BASE_URL}/api/health",
        check=False,
    )
    sh(
        f"curl -sS -o NUL -w 'h5_root %{{http_code}}\\n' {BASE_URL}/",
        check=False,
    )
    sh(
        f"curl -sS -o NUL -w 'h5_ai_home %{{http_code}}\\n' {BASE_URL}/ai-home",
        check=False,
    )
    sh(
        f"curl -sS -o NUL -w 'h5_health_profile %{{http_code}}\\n' {BASE_URL}/health-profile",
        check=False,
    )
    sh(
        f"curl -sS -o NUL -w 'admin %{{http_code}}\\n' {BASE_URL}/admin/",
        check=False,
    )

    print("\n" + "=" * 60)
    print("[BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1] 部署完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
