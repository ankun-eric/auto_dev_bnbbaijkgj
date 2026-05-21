"""[PRD-HSC-OPTIM-V3-20260521] 健康自查功能优化 V3 部署脚本。

将本次新增/修改的文件上传到部署服务器，触发 backend + admin-web + h5-web 重建，
并执行后端 pytest + HTTP 烟雾测试 + 11 个验收用例校验。
"""
from __future__ import annotations

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
    # ===== 后端 =====
    ("backend/app/main.py", f"{DEPLOY_DIR}/backend/app/main.py"),
    ("backend/app/models/models.py", f"{DEPLOY_DIR}/backend/app/models/models.py"),
    ("backend/app/api/questionnaire.py", f"{DEPLOY_DIR}/backend/app/api/questionnaire.py"),
    ("backend/app/schemas/questionnaire.py", f"{DEPLOY_DIR}/backend/app/schemas/questionnaire.py"),
    ("backend/app/schemas/function_button.py", f"{DEPLOY_DIR}/backend/app/schemas/function_button.py"),
    (
        "backend/app/services/prd_hsc_optim_v3_migration.py",
        f"{DEPLOY_DIR}/backend/app/services/prd_hsc_optim_v3_migration.py",
    ),
    (
        "backend/tests/test_hsc_optim_v3_20260521.py",
        f"{DEPLOY_DIR}/backend/tests/test_hsc_optim_v3_20260521.py",
    ),
    # ===== Admin Web =====
    (
        "admin-web/src/app/(admin)/function-buttons/page.tsx",
        f"{DEPLOY_DIR}/admin-web/src/app/(admin)/function-buttons/page.tsx",
    ),
    # ===== H5 =====
    (
        "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
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
        "h5-web/src/app/health-self-check/result/[id]/page.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/health-self-check/result/[id]/page.tsx",
    ),
    ("h5-web/src/lib/cta-router.ts", f"{DEPLOY_DIR}/h5-web/src/lib/cta-router.ts"),
    # ===== 小程序 =====
    (
        "miniprogram/components/questionnaire-result-card/index.js",
        f"{DEPLOY_DIR}/miniprogram/components/questionnaire-result-card/index.js",
    ),
    (
        "miniprogram/components/questionnaire-result-card/index.wxml",
        f"{DEPLOY_DIR}/miniprogram/components/questionnaire-result-card/index.wxml",
    ),
    (
        "miniprogram/components/questionnaire-result-card/index.wxss",
        f"{DEPLOY_DIR}/miniprogram/components/questionnaire-result-card/index.wxss",
    ),
    # ===== Flutter APP =====
    (
        "flutter_app/lib/widgets/ai_chat/questionnaire_result_card.dart",
        f"{DEPLOY_DIR}/flutter_app/lib/widgets/ai_chat/questionnaire_result_card.dart",
    ),
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
    print("[PRD-HSC-OPTIM-V3] 部署开始")
    print(f"  Host:       {HOST}")
    print(f"  DeployDir:  {DEPLOY_DIR}")
    print(f"  BaseURL:    {BASE_URL}")
    print("=" * 60)

    cli = make_ssh()
    try:
        # 1) 上传文件
        print("\n--- 步骤 1：上传变更文件 ---")
        for local, remote in FILES_TO_UPLOAD:
            upload(cli, local, remote)

        # 2) build & up
        print("\n--- 步骤 2：docker compose build & up backend + admin-web + h5-web ---")
        rc, _ = run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose build backend admin-web h5-web 2>&1 | tail -150",
            timeout=3000,
        )
        if rc != 0:
            print("⚠️ docker compose build 返回非 0，仍将尝试 up")
        run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose up -d backend admin-web h5-web 2>&1 | tail -30",
            timeout=600,
        )

        # 3) 等待后端启动 + 检查迁移日志
        print("\n--- 步骤 3：等待 25s 后检查迁移日志 ---")
        time.sleep(25)
        run(
            cli,
            f"docker logs --tail 600 {PROJECT_ID}-backend 2>&1 | "
            "grep -E 'hsc_optim_v3|render-meta|hsc-ai-task' || true",
            timeout=60,
        )

        # 4) HTTP 探活
        print("\n--- 步骤 4：HTTP 探活 ---")
        for path in [
            "/api/health",
            "/",
            "/admin/",
            "/health-self-check/result/9999999",
        ]:
            run(
                cli,
                f"curl -sk -o /dev/null -w '{path} HTTP_%{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=60,
            )

        # 5) 远端 pytest
        print("\n--- 步骤 5：远端 pytest（test_hsc_optim_v3_20260521.py） ---")
        run(
            cli,
            f"docker exec {PROJECT_ID}-backend python -m pytest "
            f"tests/test_hsc_optim_v3_20260521.py -v --no-header 2>&1 | tail -200",
            timeout=600,
        )

        print("\n" + "=" * 60)
        print("[PRD-HSC-OPTIM-V3] 部署完成")
        print("=" * 60)
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
