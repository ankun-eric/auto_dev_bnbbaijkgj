"""[PRD-432 2026-05-09] AI 回答顶部「咨询对象档案」折叠卡片 部署脚本。

部署内容：
- backend/app/api/consultant_profile_card.py (NEW: GET /api/v1/consultant/{id}/profile_card 等)
- backend/app/main.py (启动期 ALTER TABLE 迁移 + 注册新路由)
- h5-web/src/components/ai-chat/ProfileCard.tsx (NEW)
- h5-web/src/components/ai-chat/MedicationDrawer.tsx (NEW)
- h5-web/src/app/(ai-chat)/ai-home/page.tsx (注入 ProfileCard)
- h5-web/src/app/chat/[sessionId]/page.tsx (注入 ProfileCard)
- miniprogram/components/profile-card/* (NEW)
- miniprogram/components/medication-drawer/* (NEW)
- miniprogram/pages/chat/index.{json,js,wxml}
- flutter_app/lib/widgets/ai_profile_card.dart (NEW)
- flutter_app/lib/screens/ai/chat_screen.dart (注入 AiProfileCard)
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
    "backend/app/api/consultant_profile_card.py",
    "backend/app/main.py",
    "h5-web/src/components/ai-chat/ProfileCard.tsx",
    "h5-web/src/components/ai-chat/MedicationDrawer.tsx",
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    "h5-web/src/app/chat/[sessionId]/page.tsx",
    "miniprogram/components/profile-card/index.json",
    "miniprogram/components/profile-card/index.js",
    "miniprogram/components/profile-card/index.wxml",
    "miniprogram/components/profile-card/index.wxss",
    "miniprogram/components/medication-drawer/index.json",
    "miniprogram/components/medication-drawer/index.js",
    "miniprogram/components/medication-drawer/index.wxml",
    "miniprogram/components/medication-drawer/index.wxss",
    "miniprogram/pages/chat/index.json",
    "miniprogram/pages/chat/index.js",
    "miniprogram/pages/chat/index.wxml",
    "flutter_app/lib/widgets/ai_profile_card.dart",
    "flutter_app/lib/screens/ai/chat_screen.dart",
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 1200) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:240]}")
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

    for rel in FILES:
        local_path = Path(rel)
        remote = f"{PROJECT_DIR}/{rel}"
        if not local_path.exists():
            print(f"[skip 不存在] {rel}")
            continue
        remote_dir = "/".join(remote.split("/")[:-1])
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            run(ssh, f"mkdir -p '{remote_dir}'")
        print(f"\n[上传] {rel}")
        for attempt in range(4):
            try:
                sftp.put(str(local_path), remote)
                break
            except Exception as e:
                print(f"  上传失败 ({attempt+1}/4): {e}")
                if attempt == 3:
                    raise
                time.sleep(2)

    print("\n[backend rebuild]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -60",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend", timeout=180)

    print("\n[h5-web rebuild]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -60",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web", timeout=180)

    print("\n等待 backend / h5-web 启动...")
    time.sleep(20)

    smoke_urls = [
        "/api/health",
        "/api/ai-home-config",
        "/",
        "/ai-home",
        "/api/v1/consultant/0/profile_card",
        "/api/v1/consultant/0/medications",
    ]
    print("\n[Smoke]")
    for u in smoke_urls:
        run(ssh, f"curl -s -o /dev/null -w '{u}=%{{http_code}}\\n' '{BASE_URL}{u}'")

    print("\n[Verify - 新列已迁移]")
    run(
        ssh,
        f"docker exec {DEPLOY_ID}-backend python -c \"import asyncio; from app.core.database import async_session; from sqlalchemy import text;\\n"
        f"async def main():\\n    async with async_session() as db:\\n        r = await db.execute(text('SHOW COLUMNS FROM health_profiles LIKE \\\\'%_is_none\\\\''));\\n        print(r.all());\\n        r2 = await db.execute(text('SHOW COLUMNS FROM chat_messages LIKE \\\\'consultant_target_id\\\\''));\\n        print(r2.all())\\n\\nasyncio.run(main())\" 2>&1 | tail -10",
        timeout=60,
    )

    print("\n[Verify - h5 SSR HTML 含 ProfileCard testid]")
    run(
        ssh,
        f"curl -sL '{BASE_URL}/ai-home' | grep -oE 'ai-profile-card|ai-home-profile-card-wrapper' | sort -u",
        timeout=30,
    )

    sftp.close()
    ssh.close()
    print("\n[OK] PRD-432 部署完成")


if __name__ == "__main__":
    main()
