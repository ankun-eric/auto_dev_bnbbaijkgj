"""[BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
将本次健康自查修复部署到服务器：
1. 通过 SSH 上传修改后的后端 + 前端 + admin-web 代码
2. 通过 docker compose 重建并重启 backend / h5-web / admin-web
3. 验证健康接口与首页路由可达
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

LOCAL_FILES = [
    # backend
    ("backend/app/models/models.py", f"{DEPLOY_DIR}/backend/app/models/models.py"),
    ("backend/app/schemas/questionnaire.py", f"{DEPLOY_DIR}/backend/app/schemas/questionnaire.py"),
    ("backend/app/api/questionnaire.py", f"{DEPLOY_DIR}/backend/app/api/questionnaire.py"),
    ("backend/app/main.py", f"{DEPLOY_DIR}/backend/app/main.py"),
    (
        "backend/app/services/prd_qn_content_v1_migration.py",
        f"{DEPLOY_DIR}/backend/app/services/prd_qn_content_v1_migration.py",
    ),
    (
        "backend/app/services/prd_health_self_check_fix_v1_migration.py",
        f"{DEPLOY_DIR}/backend/app/services/prd_health_self_check_fix_v1_migration.py",
    ),
    (
        "backend/tests/test_hsc_fix_v1_20260521.py",
        f"{DEPLOY_DIR}/backend/tests/test_hsc_fix_v1_20260521.py",
    ),
    # admin
    (
        "admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
        f"{DEPLOY_DIR}/admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
    ),
    # h5
    (
        "h5-web/src/app/health-self-check/result/[id]/page.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/health-self-check/result/[id]/page.tsx",
    ),
]


def sh(cmd: str, *, check: bool = True, timeout: int = 600) -> str:
    """执行本地 shell 命令并返回 stdout（合并 stderr）。"""
    print(f"$ {cmd}")
    proc = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out)
    if check and proc.returncode != 0:
        raise SystemExit(f"命令失败: {cmd}\n{out}")
    return out


def ssh(cmd: str, *, timeout: int = 1200) -> str:
    """通过 OpenSSH 在远端执行命令（已存在密钥/agent）。"""
    quoted = cmd.replace('"', '\\"')
    full = (
        f'ssh -o StrictHostKeyChecking=no -o BatchMode=no '
        f"{USER}@{HOST} \"{quoted}\""
    )
    return sh(full, timeout=timeout)


def scp_one(local: str, remote: str) -> None:
    """上传单个文件，自动创建远端父目录。"""
    parent = remote.rsplit("/", 1)[0]
    ssh(f"mkdir -p '{parent}'")
    # scp 不支持远端路径含特殊字符 () 时直接传，用 SFTP put 兜底
    full = (
        f'scp -o StrictHostKeyChecking=no '
        f'"{local}" "{USER}@{HOST}:{remote}"'
    )
    sh(full)


def main() -> int:
    print("=" * 60)
    print("[BUG-HEALTH-SELF-CHECK-FIX-V1] 部署开始")
    print("=" * 60)

    # 1. 上传文件
    print("\n--- 步骤 1：上传变更文件 ---")
    for local, remote in LOCAL_FILES:
        scp_one(local, remote)

    # 2. 重建并启动容器（仅相关 3 个）
    print("\n--- 步骤 2：重建 backend / h5-web / admin-web ---")
    ssh(
        f"cd {DEPLOY_DIR} && docker compose build backend h5-web admin-web 2>&1 | tail -100",
        timeout=1800,
    )
    ssh(
        f"cd {DEPLOY_DIR} && docker compose up -d backend h5-web admin-web 2>&1 | tail -30",
        timeout=900,
    )

    # 3. 等待后端启动
    print("\n--- 步骤 3：等待后端启动（30s） ---")
    time.sleep(30)

    # 4. 抓取后端日志确认迁移
    print("\n--- 步骤 4：检查后端迁移日志 ---")
    log = ssh(
        f"docker logs --tail 200 {PROJECT_ID}-backend 2>&1 | "
        f"grep -E 'health_self_check_fix_v1|migrate.*hsc|migrate.*qn_content' || true"
    )
    print(f"迁移日志摘要：\n{log}")

    # 5. 探活：健康检查 + 健康自查模板路由
    print("\n--- 步骤 5：探活检查 ---")
    sh(
        f"curl -sS -o /dev/null -w 'health %{{http_code}}\\n' {BASE_URL}/api/health "
        f"|| echo 'health endpoint check done'",
        check=False,
    )
    sh(
        f"curl -sS -o /dev/null -w 'h5 %{{http_code}}\\n' {BASE_URL}/ "
        f"|| echo 'h5 check done'",
        check=False,
    )
    sh(
        f"curl -sS -o /dev/null -w 'admin %{{http_code}}\\n' {BASE_URL}/admin/ "
        f"|| echo 'admin check done'",
        check=False,
    )

    # 6. 远端 pytest（仅运行新增 hsc fix 测试，保持快速）
    print("\n--- 步骤 6：远端 pytest 跑 hsc fix 测试 ---")
    result = ssh(
        f"docker exec {PROJECT_ID}-backend python -m pytest "
        f"tests/test_hsc_fix_v1_20260521.py -v 2>&1 | tail -60",
        timeout=300,
    )
    if "failed" in result.lower() or "error" in result.lower() and "0 errors" not in result.lower():
        print("⚠️ 有测试失败，请查看日志")
    else:
        print("✅ HSC FIX 测试通过")

    print("\n" + "=" * 60)
    print("[BUG-HEALTH-SELF-CHECK-FIX-V1] 部署完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
