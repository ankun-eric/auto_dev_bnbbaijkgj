"""[PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 部署脚本

把"体质测评 3 大 Bug 修复 + 通用卡片消息协议 + 6 屏沉浸式详情页通用框架"
本次改动的后端 + h5-web + miniprogram + flutter_app 文件上传到服务器，
并重启对应容器。
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
    "backend/app/api/tcm.py",
    "backend/app/schemas/tcm.py",
    "backend/tests/test_tcm_card_msg_protocol_v1_20260520.py",
]

H5_FILES = [
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    "h5-web/src/components/ai-chat/UniversalQuestionnaireResultCard.tsx",
    "h5-web/src/components/ai-chat/FollowupChipsRow.tsx",
]

MP_FILES = [
    "miniprogram/pages/chat/index.json",
    "miniprogram/pages/chat/index.wxml",
    "miniprogram/pages/chat/index.js",
    "miniprogram/pages/tcm/index.js",
    "miniprogram/components/questionnaire-result-card/index.json",
    "miniprogram/components/questionnaire-result-card/index.js",
    "miniprogram/components/questionnaire-result-card/index.wxml",
    "miniprogram/components/questionnaire-result-card/index.wxss",
    "miniprogram/components/followup-chips-row/index.json",
    "miniprogram/components/followup-chips-row/index.js",
    "miniprogram/components/followup-chips-row/index.wxml",
    "miniprogram/components/followup-chips-row/index.wxss",
]

FLUTTER_FILES = [
    "flutter_app/lib/models/chat_message.dart",
    "flutter_app/lib/widgets/ai_chat/questionnaire_result_card.dart",
    "flutter_app/lib/widgets/ai_chat/followup_chips_row.dart",
    "flutter_app/lib/screens/ai/chat_screen.dart",
    "flutter_app/lib/screens/health/tcm_screen.dart",
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
        print(out[-2500:])
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
    print(f"=== Deploy TCM-CARD-MSG-PROTOCOL-V1 to {HOST} ===")
    ssh = ssh_connect()

    print("\n--- Step 1: upload backend files ---")
    upload_files(ssh, BACKEND_FILES)

    print("\n--- Step 2: upload h5-web files ---")
    upload_files(ssh, H5_FILES)

    print("\n--- Step 3: upload miniprogram files ---")
    upload_files(ssh, MP_FILES)

    print("\n--- Step 4: upload flutter_app files (for source-of-truth, no build here) ---")
    upload_files(ssh, FLUTTER_FILES)

    print("\n--- Step 5: rebuild backend image (source mounted via image build) ---")
    cmd = (
        f"cd {PROJECT_DIR} && "
        f"docker compose build backend 2>&1 | tail -30 && "
        f"docker compose up -d backend 2>&1 | tail -10"
    )
    run(ssh, cmd, timeout=900)
    time.sleep(10)

    print("\n--- Step 6: wait backend healthy ---")
    for i in range(30):
        code, out, _ = run(
            ssh,
            f"docker logs --tail 60 {PROJECT_UUID}-backend 2>&1 | tail -60",
            timeout=60,
        )
        if "Application startup complete" in out or "Uvicorn running" in out:
            print("[backend] startup complete")
            break
        time.sleep(3)

    print("\n--- Step 7: rebuild & restart h5-web ---")
    cmd = (
        f"cd {PROJECT_DIR} && "
        f"docker compose build h5-web 2>&1 | tail -30 && "
        f"docker compose up -d h5-web 2>&1 | tail -10"
    )
    run(ssh, cmd, timeout=1500)
    time.sleep(8)

    print("\n--- Step 8: health check ---")
    base = f"http://localhost/autodev/{PROJECT_UUID}"
    run(
        ssh,
        f"curl -s -o /dev/null -w 'backend_templates:%{{http_code}}\\n' '{base}/api/questionnaire/templates'",
        timeout=30,
    )
    run(
        ssh,
        f"curl -s -o /dev/null -w 'h5_root:%{{http_code}}\\n' '{base}/'",
        timeout=30,
    )

    print("\n--- Step 9: ensure pytest file is inside backend container ---")
    # rebuild 后 image 已包含新 test 文件（COPY tests/）；但稳妥起见 docker cp 一份
    run(
        ssh,
        (
            f"docker cp {PROJECT_DIR}/backend/tests/test_tcm_card_msg_protocol_v1_20260520.py "
            f"{PROJECT_UUID}-backend:/app/tests/test_tcm_card_msg_protocol_v1_20260520.py"
        ),
        timeout=30,
    )

    print("\n--- Step 10: install pytest (if missing) + run pytest ---")
    run(
        ssh,
        (
            f"docker exec {PROJECT_UUID}-backend bash -lc "
            f"'python -c \"import pytest\" 2>/dev/null || pip install --quiet pytest httpx 2>&1 | tail -5'"
        ),
        timeout=180,
    )
    run(
        ssh,
        (
            f"docker exec {PROJECT_UUID}-backend bash -lc "
            f"'cd /app && python -m pytest tests/test_tcm_card_msg_protocol_v1_20260520.py "
            f"-v --tb=short -p no:warnings 2>&1 | tail -120'"
        ),
        timeout=600,
    )

    ssh.close()
    print("=== Deploy done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
