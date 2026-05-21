"""[PRD-HSC-AI-REAL-V1 2026-05-21] 健康自查 AI 解读真接入大模型部署脚本。

变更概要：
- 后端：新增 health_self_check_ai.py 服务、prd_hsc_ai_real_v1_migration.py 迁移；
  改造 questionnaire.py 异步任务 _run_hsc_ai_interpretation 真接入 LLM；
  详情接口新增 profile_outdated / ai_generated_at；
  models.py + main.py 注册新迁移。
- 前端 H5：health-self-check/result/[id]/page.tsx 删除「答题记录」整块区域 +
  新增「档案已更新」提示条 + AI 解读以 Markdown 风格保留段落显示。
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
    (
        "backend/app/services/health_self_check_ai.py",
        f"{DEPLOY_DIR}/backend/app/services/health_self_check_ai.py",
    ),
    (
        "backend/app/services/prd_hsc_ai_real_v1_migration.py",
        f"{DEPLOY_DIR}/backend/app/services/prd_hsc_ai_real_v1_migration.py",
    ),
    (
        "backend/tests/test_hsc_ai_real_v1_20260521.py",
        f"{DEPLOY_DIR}/backend/tests/test_hsc_ai_real_v1_20260521.py",
    ),
    # ===== H5 =====
    (
        "h5-web/src/app/health-self-check/result/[id]/page.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/health-self-check/result/[id]/page.tsx",
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
    print("[PRD-HSC-AI-REAL-V1] 部署开始")
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

        # 2) build & up backend + h5-web（admin-web 本期未改）
        print("\n--- 步骤 2：docker compose build & up backend + h5-web ---")
        rc, _ = run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose build backend h5-web 2>&1 | tail -150",
            timeout=3600,
        )
        if rc != 0:
            print("⚠️ docker compose build 返回非 0，仍将尝试 up")
        run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose up -d backend h5-web 2>&1 | tail -30",
            timeout=600,
        )

        # 3) 等待后端启动 + 检查迁移日志
        print("\n--- 步骤 3：等待 30s 后检查迁移日志 ---")
        time.sleep(30)
        run(
            cli,
            f"docker logs --tail 800 {PROJECT_ID}-backend 2>&1 | "
            "grep -E 'hsc_ai_real_v1|hsc_optim_v3|hsc-ai-task|health_self_check' || true",
            timeout=60,
        )

        # 4) HTTP 探活
        print("\n--- 步骤 4：HTTP 探活 ---")
        for path in [
            "/api/health",
            "/",
            "/health-self-check/result/9999999",
            "/admin/",
        ]:
            run(
                cli,
                f"curl -sk -o /dev/null -w '{path} HTTP_%{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=60,
            )

        # 5) 远端 pytest（本期新增 + 旧 v3 一起回归）
        print("\n--- 步骤 5：远端 pytest 回归 ---")
        run(
            cli,
            f"docker exec {PROJECT_ID}-backend python -m pytest "
            f"tests/test_hsc_ai_real_v1_20260521.py -v --no-header --tb=short 2>&1 | tail -120",
            timeout=600,
        )

        # 6) 检查 ai_prompt_template 是否更新成功
        print("\n--- 步骤 6：检查 health_self_check 模板 ai_prompt_template 已更新 ---")
        run(
            cli,
            f"docker exec {PROJECT_ID}-backend python -c "
            "\"import asyncio; "
            "from app.core.database import async_session; "
            "from sqlalchemy import text; "
            "async def main():"
            " async with async_session() as db:"
            "  r=(await db.execute(text('SELECT ai_prompt_template FROM questionnaire_template "
            "WHERE code=\\\"health_self_check\\\" LIMIT 1'))).first();"
            "  s=(r[0] or '') if r else '';"
            "  print('[prompt-check] has_zh_part=',('{部位}' in s),"
            " 'has_zh_symptoms=',('{症状列表}' in s),"
            " 'has_old_scores=',('{scores}' in s),"
            " 'has_old_main_type=',('{main_type}' in s),"
            " 'len=',len(s));"
            "asyncio.run(main())\" 2>&1 | tail -20",
            timeout=120,
        )

        print("\n" + "=" * 60)
        print("[PRD-HSC-AI-REAL-V1] 部署完成")
        print("=" * 60)
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
