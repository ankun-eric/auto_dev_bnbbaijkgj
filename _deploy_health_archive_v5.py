"""[PRD-HEALTH-ARCHIVE-V5-20260521] 健康档案与就医资料优化部署脚本。"""
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
    # backend 新增 + 修改
    ("backend/app/api/health_archive_v5.py", f"{DEPLOY_DIR}/backend/app/api/health_archive_v5.py"),
    ("backend/app/models/health_archive_v5.py", f"{DEPLOY_DIR}/backend/app/models/health_archive_v5.py"),
    ("backend/app/services/prd_health_archive_v5_migration.py", f"{DEPLOY_DIR}/backend/app/services/prd_health_archive_v5_migration.py"),
    ("backend/app/main.py", f"{DEPLOY_DIR}/backend/app/main.py"),
    ("backend/app/api/medication_plans_v1.py", f"{DEPLOY_DIR}/backend/app/api/medication_plans_v1.py"),
    ("backend/tests/test_health_archive_v5_20260521.py", f"{DEPLOY_DIR}/backend/tests/test_health_archive_v5_20260521.py"),
    # h5-web 新增
    ("h5-web/src/lib/api/health-archive-v5.ts", f"{DEPLOY_DIR}/h5-web/src/lib/api/health-archive-v5.ts"),
    ("h5-web/src/app/health-alerts/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/health-alerts/page.tsx"),
    ("h5-web/src/app/medical-records/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/medical-records/page.tsx"),
    ("h5-web/src/app/medical-records/[id]/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/medical-records/[id]/page.tsx"),
    ("h5-web/src/app/medical-records/trash/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/medical-records/trash/page.tsx"),
    # h5-web 修改
    ("h5-web/src/app/health-profile/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/health-profile/page.tsx"),
    ("h5-web/src/app/devices/member/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/devices/member/page.tsx"),
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
    print("[PRD-HEALTH-ARCHIVE-V5-20260521] 部署开始")
    print(f"  Host:       {HOST}")
    print(f"  DeployDir:  {DEPLOY_DIR}")
    print(f"  BaseURL:    {BASE_URL}")
    print("=" * 60)

    cli = make_ssh()
    try:
        print("\n--- 步骤 1：上传变更文件 ---")
        for local, remote in FILES_TO_UPLOAD:
            upload(cli, local, remote)

        print("\n--- 步骤 2：docker compose build & up backend + h5-web ---")
        rc, _ = run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose build backend h5-web 2>&1 | tail -150",
            timeout=2400,
        )
        if rc != 0:
            print("⚠️ docker compose build 返回非 0，仍将尝试 up")
        run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose up -d backend h5-web 2>&1 | tail -30",
            timeout=600,
        )

        print("\n--- 步骤 3：等待 30s 后检查迁移日志 ---")
        time.sleep(30)
        run(
            cli,
            f"docker logs --tail 400 {PROJECT_ID}-backend 2>&1 | "
            "grep -E 'health_archive_v5|health_alerts|medical_records' || true",
            timeout=60,
        )

        print("\n--- 步骤 4：HTTP 探活 ---")
        for path in [
            "/api/health",
            "/",
            "/health-profile",
            "/health-alerts",
            "/medical-records",
            "/api/health-archive-v5/overview",  # 期望 401（未带 token）但能命中后端
        ]:
            run(
                cli,
                f"curl -sk -o /dev/null -w '{path} HTTP_%{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=60,
            )

        print("\n--- 步骤 5：远端 pytest（test_health_archive_v5_20260521.py） ---")
        run(
            cli,
            f"docker exec {PROJECT_ID}-backend python -m pytest "
            f"tests/test_health_archive_v5_20260521.py -v --no-header 2>&1 | tail -120",
            timeout=300,
        )

        print("\n" + "=" * 60)
        print("[PRD-HEALTH-ARCHIVE-V5-20260521] 部署完成")
        print("=" * 60)
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
