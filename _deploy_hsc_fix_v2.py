"""[BUG-HSC-FIX-V2-20260521] 集中修复部署脚本

把以下变更部署到服务器并触发重建：
  - 后端：questionnaire.py / prompt_renderer.py / prd_health_self_check_legacy_offline_v1_migration.py / main.py
  - 前端 H5：health-self-check/result/[id]/page.tsx / ErrorBoundary.tsx / QuestionnaireDrawer.tsx / UniversalQuestionnaireResultCard.tsx / ai-home/page.tsx
  - 后台 admin：questionnaire-templates/page.tsx / layout.tsx
  - 删除：admin 老页面目录 health-check-templates / body-part-dict
  - 后端测试：test_hsc_fix_v2_20260521.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"


FILES_TO_UPLOAD: list[tuple[str, str]] = [
    # backend
    ("backend/app/api/questionnaire.py", f"{DEPLOY_DIR}/backend/app/api/questionnaire.py"),
    ("backend/app/main.py", f"{DEPLOY_DIR}/backend/app/main.py"),
    (
        "backend/app/services/prompt_renderer.py",
        f"{DEPLOY_DIR}/backend/app/services/prompt_renderer.py",
    ),
    (
        "backend/app/services/prd_health_self_check_legacy_offline_v1_migration.py",
        f"{DEPLOY_DIR}/backend/app/services/prd_health_self_check_legacy_offline_v1_migration.py",
    ),
    (
        "backend/tests/test_hsc_fix_v2_20260521.py",
        f"{DEPLOY_DIR}/backend/tests/test_hsc_fix_v2_20260521.py",
    ),
    # h5-web
    (
        "h5-web/src/app/health-self-check/result/[id]/page.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/health-self-check/result/[id]/page.tsx",
    ),
    (
        "h5-web/src/components/ErrorBoundary.tsx",
        f"{DEPLOY_DIR}/h5-web/src/components/ErrorBoundary.tsx",
    ),
    (
        "h5-web/src/components/ai-chat/QuestionnaireDrawer.tsx",
        f"{DEPLOY_DIR}/h5-web/src/components/ai-chat/QuestionnaireDrawer.tsx",
    ),
    (
        "h5-web/src/components/ai-chat/UniversalQuestionnaireResultCard.tsx",
        f"{DEPLOY_DIR}/h5-web/src/components/ai-chat/UniversalQuestionnaireResultCard.tsx",
    ),
    (
        "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    ),
    # admin-web
    (
        "admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
        f"{DEPLOY_DIR}/admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
    ),
    (
        "admin-web/src/app/(admin)/layout.tsx",
        f"{DEPLOY_DIR}/admin-web/src/app/(admin)/layout.tsx",
    ),
]


# 要在远端删除的目录（老页面）
DIRS_TO_DELETE_REMOTE: list[str] = [
    f"{DEPLOY_DIR}/admin-web/src/app/(admin)/health-check-templates",
    f"{DEPLOY_DIR}/admin-web/src/app/(admin)/body-part-dict",
]


def make_ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 1800) -> tuple[int, str]:
    print(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    rc = stdout.channel.recv_exit_status()
    combined = (out + err).rstrip()
    if combined:
        # 截断超长输出
        print(combined[-4000:])
    return rc, combined


def upload(cli: paramiko.SSHClient, local: str, remote: str) -> None:
    p = Path(local)
    if not p.exists():
        print(f"  ⚠️ 本地文件不存在，跳过：{local}")
        return
    parent = remote.rsplit("/", 1)[0]
    run(cli, f"mkdir -p '{parent}'", timeout=60)
    sftp = cli.open_sftp()
    try:
        sftp.put(str(p), remote)
        print(f"  ✅ uploaded {local} -> {remote}")
    finally:
        sftp.close()


def main() -> int:
    print("=" * 60)
    print("[BUG-HSC-FIX-V2] 部署开始")
    print(f"  Host:       {HOST}")
    print(f"  DeployDir:  {DEPLOY_DIR}")
    print(f"  BaseURL:    {BASE_URL}")
    print("=" * 60)

    cli = make_ssh()
    try:
        # 1) 上传变更文件
        print("\n--- 步骤 1：上传变更文件 ---")
        for local, remote in FILES_TO_UPLOAD:
            upload(cli, local, remote)

        # 2) 删除老页面目录
        print("\n--- 步骤 2：删除 admin 老页面目录 ---")
        for d in DIRS_TO_DELETE_REMOTE:
            run(cli, f"rm -rf '{d}'", timeout=60)

        # 3) 重建并启动 backend / h5-web / admin-web 容器
        print("\n--- 步骤 3：docker compose build & up ---")
        rc, _ = run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose build backend h5-web admin-web 2>&1 | tail -120",
            timeout=2400,
        )
        if rc != 0:
            print("⚠️ docker compose build 返回非 0，将继续 up 尝试")
        run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose up -d backend h5-web admin-web 2>&1 | tail -30",
            timeout=600,
        )

        # 4) 等待后端启动 + 检查迁移日志
        print("\n--- 步骤 4：等待 35s 后检查迁移日志 ---")
        time.sleep(35)
        run(
            cli,
            f"docker logs --tail 300 {PROJECT_ID}-backend 2>&1 | "
            "grep -E 'hsc_legacy_offline_v1|placeholder|prompt_renderer' || true",
            timeout=60,
        )

        # 5) 探活
        print("\n--- 步骤 5：探活 ---")
        for path in ["/api/health", "/", "/admin/", "/api/questionnaire/placeholder-catalog"]:
            run(
                cli,
                f"curl -sk -o /dev/null -w '{path} HTTP_%{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=60,
            )

        # 6) 远端 pytest 跑新测试
        print("\n--- 步骤 6：远端 pytest（test_hsc_fix_v2_20260521.py） ---")
        run(
            cli,
            f"docker exec {PROJECT_ID}-backend python -m pytest "
            f"tests/test_hsc_fix_v2_20260521.py -v --no-header 2>&1 | tail -80",
            timeout=300,
        )

        print("\n" + "=" * 60)
        print("[BUG-HSC-FIX-V2] 部署完成")
        print("=" * 60)
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
