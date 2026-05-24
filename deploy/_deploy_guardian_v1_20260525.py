"""[守护人体系 PRD v1.1 2026-05-25] 部署脚本

改动文件：
  backend/app/api/guardian_system.py            - 新增（守护人体系核心 API）
  backend/app/models/models.py                  - FamilyManagement 新增 is_primary_guardian/priority_order
  backend/app/services/schema_sync.py           - 新增 _sync_guardian_system_v1
  backend/app/main.py                           - 注册 guardian_system 路由
  backend/tests/test_guardian_system_v1.py      - 自动化测试
  h5-web/src/app/guardian-system/page.tsx       - 新增（H5 守护人体系页面）
  admin-web/src/app/(admin)/guardian-relations/page.tsx - 新增（后台守护关系查询）
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
    # backend
    ("backend/app/api/guardian_system.py", "backend/app/api/guardian_system.py"),
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/services/schema_sync.py", "backend/app/services/schema_sync.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/tests/test_guardian_system_v1.py", "backend/tests/test_guardian_system_v1.py"),
    # h5-web
    ("h5-web/src/app/guardian-system/page.tsx",
     "h5-web/src/app/guardian-system/page.tsx"),
    # admin-web
    ("admin-web/src/app/(admin)/guardian-relations/page.tsx",
     "admin-web/src/app/(admin)/guardian-relations/page.tsx"),
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
        h5_container = f"{DEPLOY_ID}-h5-web"
        admin_container = f"{DEPLOY_ID}-admin-web"

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        # ── 1. backend：docker cp + restart 触发 schema_sync 迁移 ──
        print("\n--- docker cp backend 文件到容器 ---")
        for local_rel, _ in FILES:
            if not local_rel.startswith("backend/app/"):
                continue
            host_abs = f"{PROJ_DIR}/{local_rel}"
            in_container = "/app/" + local_rel[len("backend/"):]
            run(client,
                f"docker cp '{host_abs}' '{backend_container}:{in_container}' 2>&1",
                ignore_err=True, show=False)
        # tests
        run(client,
            f"docker cp '{PROJ_DIR}/backend/tests/test_guardian_system_v1.py' "
            f"'{backend_container}:/app/tests/test_guardian_system_v1.py' 2>&1",
            ignore_err=True, show=False)

        print("\n--- 重启 backend 容器（触发 schema_sync 自动迁移） ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} restart backend 2>&1 | tail -10",
            timeout=240, ignore_err=True)

        # 等待就绪
        print("\n--- 等待 backend 就绪 ---")
        ready = False
        for i in range(80):
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
            print("WARN: backend not ready in 240s, continuing anyway")

        # 抓启动日志，确认迁移
        print("\n--- backend 日志：guardian 迁移确认 ---")
        run(client,
            f"docker logs --tail 300 {backend_container} 2>&1 | "
            f"grep -E 'guardian|is_primary_guardian|priority_order|FamilyManagement' | tail -30",
            ignore_err=True)

        # DB 表校验
        print("\n--- DB 校验：守护人体系字段与表 ---")
        run(client,
            f"docker exec {backend_container} python -c \""
            "import asyncio; from sqlalchemy import text; from app.core.database import engine\n"
            "async def main():\n"
            "  async with engine.begin() as conn:\n"
            "    for tbl in ['guardian_transfer_requests','guardian_alert_quota_usage']:\n"
            "      r = await conn.execute(text(f\\\"SHOW TABLES LIKE '{tbl}'\\\"))\n"
            "      print(tbl, 'EXISTS' if r.fetchall() else 'MISSING')\n"
            "    for col in ['is_primary_guardian','priority_order']:\n"
            "      r = await conn.execute(text(f\\\"SHOW COLUMNS FROM family_management LIKE '{col}'\\\"))\n"
            "      print('family_management.'+col, 'EXISTS' if r.fetchall() else 'MISSING')\n"
            "asyncio.run(main())\" 2>&1 | tail -20",
            ignore_err=True)

        # 服务器内运行测试（pytest）
        print("\n--- 服务器内运行 pytest（test_guardian_system_v1） ---")
        rc, pytest_out, _ = run(client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_guardian_system_v1.py -x --no-header -q 2>&1 | tail -80",
            timeout=300, ignore_err=True)

        # 端点验证
        print("\n--- 端点验证：openapi schema 含 guardian ---")
        run(client,
            f"curl -ks '{BASE_URL}/api/openapi.json' | "
            f"python3 -c 'import json,sys; d=json.load(sys.stdin); "
            "ps=[p for p in d[\"paths\"] if \"guardian\" in p]; "
            "print(\"guardian endpoints:\", len(ps)); "
            "[print(\" -\", x) for x in ps[:30]]' 2>&1 | tail -40",
            ignore_err=True)

        # ── 2. h5-web rebuild ──
        print("\n--- rebuild h5-web ---")
        # 先尝试热复制（next dev 支持 HMR），若是 prod build 则需要 rebuild
        run(client,
            f"docker cp '{PROJ_DIR}/h5-web/src/app/guardian-system/page.tsx' "
            f"'{h5_container}:/app/src/app/guardian-system/page.tsx' 2>&1",
            ignore_err=True, show=False)
        # 触发 next 重新编译
        run(client,
            f"docker exec {h5_container} sh -c 'mkdir -p /app/src/app/guardian-system' 2>&1",
            ignore_err=True, show=False)

        # 重启 h5-web
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} restart h5-web 2>&1 | tail -3",
            timeout=120, ignore_err=True)

        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(40):
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{BASE_URL}/guardian-system' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  [{(i + 1) * 3}s] h5 /guardian-system -> {code}")
            if code in ("200", "301", "302", "307", "308"):
                break
            time.sleep(3)

        # ── 3. admin-web docker cp 新页面 ──
        run(client,
            f"docker cp '{PROJ_DIR}/admin-web/src/app/(admin)/guardian-relations/page.tsx' "
            f"'{admin_container}:/app/src/app/(admin)/guardian-relations/page.tsx' 2>&1",
            ignore_err=True, show=False)
        run(client,
            f"docker exec {admin_container} sh -c 'mkdir -p \"/app/src/app/(admin)/guardian-relations\"' 2>&1",
            ignore_err=True, show=False)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} restart admin-web 2>&1 | tail -3",
            timeout=120, ignore_err=True)

        print("\n--- 等待 admin-web 就绪 ---")
        for i in range(40):
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
        print(f"H5 Guardian:  {BASE_URL}/guardian-system")
        print(f"Admin Guardian: {BASE_URL}/admin/guardian-relations")
        print("\n[Pytest 结果摘要]")
        print(pytest_out[-2000:] if pytest_out else '(无 pytest 输出)')
    finally:
        client.close()


if __name__ == "__main__":
    main()
