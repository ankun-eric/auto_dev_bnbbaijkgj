"""[PRD-QN-CONTENT-V1 2026-05-20] 部署脚本

把"4 个问卷题库 + 健康自查 6 维度 + chips/CTA 后台配置"本次改动的后端文件
上传到服务器，并重启 backend 容器，跑迁移与远程 pytest。
"""
from __future__ import annotations

import sys
import time
import paramiko
from pathlib import Path

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_UUID}"
ROOT = Path(__file__).parent

BACKEND_FILES = [
    "backend/app/api/questionnaire.py",
    "backend/app/schemas/questionnaire.py",
    "backend/app/models/models.py",
    "backend/app/main.py",
    "backend/app/services/prd_qn_content_v1_migration.py",
    "backend/tests/test_qn_content_v1_20260520.py",
]


def ssh_connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err:
        print(f"STDERR: {err[-1500:]}")
    print(f"[exit={code}]")
    return code, out, err


def upload_files(ssh: paramiko.SSHClient, files: list[str]) -> None:
    sftp = ssh.open_sftp()
    for rel in files:
        local = ROOT / rel
        if not local.exists():
            print(f"WARN: local missing: {local}")
            continue
        remote = f"{PROJECT_DIR}/{rel}".replace("\\", "/")
        parent = remote.rsplit("/", 1)[0]
        run(ssh, f"mkdir -p '{parent}'")
        sftp.put(str(local), remote)
        print(f"  UPLOADED {rel}")
    sftp.close()


def main() -> int:
    print(f"=== Deploy QN-CONTENT-V1 to {HOST} ===")
    ssh = ssh_connect()

    print("\n--- Step 1: upload backend files ---")
    upload_files(ssh, BACKEND_FILES)

    print("\n--- Step 2: docker cp backend files into running container (no rebuild) ---")
    for rel in BACKEND_FILES:
        # 仅 backend 容器内有效，flutter/h5/miniprogram 不动
        if not rel.startswith("backend/"):
            continue
        container_path = "/app/" + rel[len("backend/"):]
        run(
            ssh,
            f"docker cp {PROJECT_DIR}/{rel} {PROJECT_UUID}-backend:{container_path}",
            timeout=30,
        )

    print("\n--- Step 3: restart backend container ---")
    run(ssh, f"docker restart {PROJECT_UUID}-backend", timeout=60)
    time.sleep(8)

    print("\n--- Step 4: wait backend healthy ---")
    for i in range(40):
        code, out, _ = run(
            ssh,
            f"docker logs --tail 80 {PROJECT_UUID}-backend 2>&1 | tail -80",
            timeout=60,
        )
        if "Application startup complete" in out or "Uvicorn running" in out:
            print("[backend] startup complete")
            break
        time.sleep(3)

    print("\n--- Step 5: check qn_content_v1 migration log ---")
    run(
        ssh,
        f"docker logs --tail 400 {PROJECT_UUID}-backend 2>&1 | grep -i 'qn_content_v1\\|qn_content' | tail -30",
        timeout=30,
    )

    print("\n--- Step 6: health check ---")
    base = f"http://localhost/autodev/{PROJECT_UUID}"
    run(
        ssh,
        f"curl -s -o /dev/null -w 'backend_templates:%{{http_code}}\\n' '{base}/api/questionnaire/templates'",
        timeout=30,
    )
    run(
        ssh,
        f"curl -s '{base}/api/questionnaire/templates/by-code/phq9' | head -c 500",
        timeout=30,
    )
    print()
    run(
        ssh,
        f"curl -s '{base}/api/questionnaire/templates/by-code/gad7' | head -c 500",
        timeout=30,
    )
    print()
    run(
        ssh,
        f"curl -s '{base}/api/questionnaire/templates/by-code/psqi' | head -c 500",
        timeout=30,
    )
    print()

    print("\n--- Step 7: run pytest in container ---")
    run(
        ssh,
        (
            f"docker exec {PROJECT_UUID}-backend bash -lc "
            f"'python -c \"import pytest\" 2>/dev/null || pip install --quiet pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -5'"
        ),
        timeout=240,
    )
    run(
        ssh,
        (
            f"docker exec {PROJECT_UUID}-backend bash -lc "
            f"'cd /app && python -m pytest tests/test_qn_content_v1_20260520.py "
            f"-v --tb=short -p no:warnings 2>&1 | tail -120'"
        ),
        timeout=600,
    )

    ssh.close()
    print("=== Deploy done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
