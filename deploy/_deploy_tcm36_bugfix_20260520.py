"""[PRD-TCM-DRAWER-V12 Bug 修复 2026-05-20] 加载问卷模板失败 / 36 题 / 卡片弹出 修复部署

改动文件：
  backend/app/api/questionnaire.py        - 422 上限放宽 + 主动追问接口
  backend/app/api/chat.py                  - TCM 上下文注入（system_prompt）
  backend/app/services/prd_tcm36_drawer_v12_migration.py - 标准化运维日志
  backend/scripts/_seed_tcm36.py           - 一次性补数脚本（新增）
  admin-web/src/app/(admin)/function-buttons/page.tsx   - page_size 200→100
  h5-web/src/app/(ai-chat)/ai-home/page.tsx             - 模板 id 空 Toast 兜底
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES = [
    ("backend/app/api/questionnaire.py",
     "backend/app/api/questionnaire.py"),
    ("backend/app/api/chat.py",
     "backend/app/api/chat.py"),
    ("backend/app/services/prd_tcm36_drawer_v12_migration.py",
     "backend/app/services/prd_tcm36_drawer_v12_migration.py"),
    ("backend/scripts/_seed_tcm36.py",
     "backend/scripts/_seed_tcm36.py"),
    ("backend/tests/test_tcm36_drawer_v12_20260520.py",
     "backend/tests/test_tcm36_drawer_v12_20260520.py"),
    ("admin-web/src/app/(admin)/function-buttons/page.tsx",
     "admin-web/src/app/(admin)/function-buttons/page.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:], flush=True)
    if show and err.strip():
        print("STDERR:", err[-1500:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    print(f"Local base: {base}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")

    try:
        sftp = client.open_sftp()
        for local_rel, remote_rel in FILES:
            local_abs = os.path.join(base, local_rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                print(f"  [SKIP] missing local: {local_abs}")
                continue
            remote_abs = f"{PROJ_DIR}/{remote_rel}"
            run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
            print(f"  upload: {local_rel} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        backend_container = f"{DEPLOY_ID}-backend"
        admin_container = f"{DEPLOY_ID}-admin-web"
        h5_container = f"{DEPLOY_ID}-h5-web"

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        # ── 1. backend：docker cp + restart 触发幂等迁移 ──
        print("\n--- docker cp backend 文件到 backend 容器 ---")
        for local_rel, _ in FILES:
            if not local_rel.startswith("backend/app/"):
                continue
            host_abs = f"{PROJ_DIR}/{local_rel}"
            in_container = "/app/" + local_rel[len("backend/"):]
            run(client,
                f"docker cp '{host_abs}' '{backend_container}:{in_container}' 2>&1",
                ignore_err=True, show=False)
        # scripts/_seed_tcm36.py
        run(client,
            f"docker exec {backend_container} mkdir -p /app/scripts 2>&1",
            ignore_err=True, show=False)
        run(client,
            f"docker cp '{PROJ_DIR}/backend/scripts/_seed_tcm36.py' "
            f"'{backend_container}:/app/scripts/_seed_tcm36.py' 2>&1",
            ignore_err=True, show=False)
        # tests
        run(client,
            f"docker cp '{PROJ_DIR}/backend/tests/test_tcm36_drawer_v12_20260520.py' "
            f"'{backend_container}:/app/tests/test_tcm36_drawer_v12_20260520.py' 2>&1",
            ignore_err=True)

        print("\n--- 重启 backend 容器（触发启动迁移） ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} restart backend 2>&1 | tail -10",
            timeout=180, ignore_err=True)

        # 等待就绪
        print("\n--- 等待 backend 就绪 ---")
        ready = False
        for i in range(60):
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{BASE_URL}/api/openapi.json' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  [{(i + 1) * 3}s] backend openapi.json -> {code}")
            if code == "200":
                ready = True
                break
            time.sleep(3)
        if not ready:
            print("WARN: backend not ready in 180s, continuing anyway")

        # 抓启动日志
        print("\n--- 抓 backend 启动日志，确认 seed ---")
        run(client,
            f"docker logs --tail 400 {backend_container} 2>&1 | grep -E 'tcm36|seed tcm_constitution|36 questions' | tail -40",
            ignore_err=True)

        # DB 校验
        print("\n--- DB 校验 questionnaire_question 题数 ---")
        run(client,
            "docker exec " + backend_container + " python -c \""
            "import asyncio; from sqlalchemy import text; from app.core.database import async_session\n"
            "async def main():\n"
            "  async with async_session() as db:\n"
            "    r = await db.execute(text(\\\"SELECT count(*) FROM questionnaire_question q JOIN questionnaire_template t ON q.template_id = t.id WHERE t.code='tcm_constitution'\\\"))\n"
            "    print('tcm_constitution question count:', r.scalar())\n"
            "asyncio.run(main())\" 2>&1 | tail -10",
            ignore_err=True)

        # ── 2. admin-web：仅当文件有更新时 rebuild ──
        print("\n--- rebuild admin-web ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} stop admin-web 2>&1 | tail -3",
            ignore_err=True)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f admin-web 2>&1 | tail -3",
            ignore_err=True)
        print("Building admin-web (5-10 min)...")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} build admin-web 2>&1 | tail -120",
            timeout=1800)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d admin-web 2>&1 | tail -10")

        # ── 3. h5-web rebuild ──
        print("\n--- rebuild h5-web ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3",
            ignore_err=True)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3",
            ignore_err=True)
        print("Building h5-web (5-10 min)...")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -120",
            timeout=1800)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{BASE_URL}/' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  [{(i + 1) * 3}s] h5 / -> {code}")
            if code in ("200", "301", "302", "307", "308"):
                break
            time.sleep(3)

        print("\n--- 等待 admin-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{BASE_URL}/admin' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  [{(i + 1) * 3}s] admin / -> {code}")
            if code in ("200", "301", "302", "307", "308"):
                break
            time.sleep(3)

        print("\nDEPLOY DONE.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
