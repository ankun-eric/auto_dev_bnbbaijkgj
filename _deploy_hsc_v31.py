"""[BUG-HSC-V31 2026-05-21] 健康自查 V3.1 三个残留 Bug 修复 - 部署脚本。

变更文件：
- backend/app/api/questionnaire.py（强化 AI 任务写库前校验）
- h5-web/src/app/(ai-chat)/ai-home/page.tsx
    1) submit handler 显式传 subject_* 4 字段
    2) 收到 render-meta 后，autoNext+per_page=1 时强制升级到 DRAWER_STEPPED
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
    ("backend/app/api/questionnaire.py", f"{DEPLOY_DIR}/backend/app/api/questionnaire.py"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
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
        print(f"  WARN local file missing, skip: {local}")
        return
    parent = remote.rsplit("/", 1)[0]
    run(cli, f"mkdir -p '{parent}'", timeout=60)
    sftp = cli.open_sftp()
    try:
        sftp.put(str(p), remote)
        print(f"  uploaded {local} -> {remote}")
    finally:
        sftp.close()


def main() -> int:
    print("=" * 60)
    print("[BUG-HSC-V31] deploy starts")
    print(f"  Host:       {HOST}")
    print(f"  DeployDir:  {DEPLOY_DIR}")
    print(f"  BaseURL:    {BASE_URL}")
    print("=" * 60)

    cli = make_ssh()
    try:
        print("\n--- step 1 upload changed files ---")
        for local, remote in FILES_TO_UPLOAD:
            upload(cli, local, remote)

        print("\n--- step 2 docker compose build & up backend + h5-web ---")
        rc, _ = run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose build backend h5-web 2>&1 | tail -200",
            timeout=2400,
        )
        if rc != 0:
            print("WARN: docker compose build returned non-zero, still try to up")
        run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose up -d backend h5-web 2>&1 | tail -30",
            timeout=600,
        )

        print("\n--- step 3 wait 25s then probe ---")
        time.sleep(25)

        print("\n--- step 4 HTTP probe ---")
        for path in [
            "/api/health",
            "/",
        ]:
            run(
                cli,
                f"curl -sk -o /dev/null -w '{path} HTTP_%{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=60,
            )

        print("\n--- step 5 db sanity check ---")
        run(
            cli,
            f"docker exec {PROJECT_ID}-db mysql -uroot -pbini_health_2026 bini_health "
            f"-e \"SELECT id,name,auto_next_enabled,presentation_container,questions_per_page "
            f"FROM chat_function_buttons WHERE ai_function_type='questionnaire' ORDER BY id DESC LIMIT 5;\" 2>&1 "
            f"| grep -v 'Using a password'",
            timeout=60,
        )

        print("\n" + "=" * 60)
        print("[BUG-HSC-V31] deploy done")
        print("=" * 60)
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
