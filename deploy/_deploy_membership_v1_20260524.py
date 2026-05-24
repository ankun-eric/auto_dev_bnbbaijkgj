"""[付费会员体系 PRD v1.1 2026-05-24] 部署脚本

改动文件：
  backend/app/models/membership_plan.py        - 新增（MembershipPlan / UserMembershipSub / FreeMemberQuota）
  backend/app/models/models.py                  - Product 新增 is_member_discount_eligible 字段
  backend/app/schemas/membership.py             - 新增（套餐/订阅/优惠计算 schema）
  backend/app/schemas/products.py               - is_member_discount_eligible 字段
  backend/app/api/membership.py                 - 新增（套餐 CRUD / 用户订阅 / 收银台优惠计算）
  backend/app/api/product_admin.py              - is_member_discount_eligible 写入与返回
  backend/app/main.py                           - 注册 membership 路由
  backend/app/services/schema_sync.py           - _sync_membership_v1 表与字段迁移
  backend/tests/test_membership_v1.py           - 自动化测试
  admin-web/src/app/(admin)/layout.tsx          - 菜单：下线"会员等级"，新增"会员管理"
  admin-web/src/app/(admin)/membership/plans/page.tsx       - 新增（套餐配置页）
  admin-web/src/app/(admin)/membership/free-quota/page.tsx  - 新增（免费额度配置页）
  admin-web/src/app/(admin)/product-system/products/page.tsx - Tab 改名 + 新增开关
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
    ("backend/app/models/membership_plan.py", "backend/app/models/membership_plan.py"),
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/schemas/membership.py", "backend/app/schemas/membership.py"),
    ("backend/app/schemas/products.py", "backend/app/schemas/products.py"),
    ("backend/app/api/membership.py", "backend/app/api/membership.py"),
    ("backend/app/api/product_admin.py", "backend/app/api/product_admin.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/app/services/schema_sync.py", "backend/app/services/schema_sync.py"),
    ("backend/tests/test_membership_v1.py", "backend/tests/test_membership_v1.py"),
    # admin-web
    ("admin-web/src/app/(admin)/layout.tsx",
     "admin-web/src/app/(admin)/layout.tsx"),
    ("admin-web/src/app/(admin)/membership/plans/page.tsx",
     "admin-web/src/app/(admin)/membership/plans/page.tsx"),
    ("admin-web/src/app/(admin)/membership/free-quota/page.tsx",
     "admin-web/src/app/(admin)/membership/free-quota/page.tsx"),
    ("admin-web/src/app/(admin)/product-system/products/page.tsx",
     "admin-web/src/app/(admin)/product-system/products/page.tsx"),
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
            f"docker cp '{PROJ_DIR}/backend/tests/test_membership_v1.py' "
            f"'{backend_container}:/app/tests/test_membership_v1.py' 2>&1",
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
        print("\n--- backend 日志：membership 迁移确认 ---")
        run(client,
            f"docker logs --tail 200 {backend_container} 2>&1 | "
            f"grep -E 'membership|free_member_quota|is_member_discount_eligible' | tail -30",
            ignore_err=True)

        # DB 表校验
        print("\n--- DB 校验：付费会员相关表 ---")
        run(client,
            f"docker exec {backend_container} python -c \""
            "import asyncio; from sqlalchemy import text; from app.core.database import engine\n"
            "async def main():\n"
            "  async with engine.begin() as conn:\n"
            "    for tbl in ['membership_plans','user_membership_subs','free_member_quota']:\n"
            "      r = await conn.execute(text(f\\\"SHOW TABLES LIKE '{tbl}'\\\"))\n"
            "      rows = r.fetchall()\n"
            "      print(tbl, 'EXISTS' if rows else 'MISSING')\n"
            "    r = await conn.execute(text(\\\"SHOW COLUMNS FROM products LIKE 'is_member_discount_eligible'\\\"))\n"
            "    print('products.is_member_discount_eligible', 'EXISTS' if r.fetchall() else 'MISSING')\n"
            "asyncio.run(main())\" 2>&1 | tail -20",
            ignore_err=True)

        # 服务器内运行测试（pytest）
        print("\n--- 服务器内运行 pytest（test_membership_v1） ---")
        run(client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_membership_v1.py -x --no-header -q 2>&1 | tail -50",
            timeout=300, ignore_err=True)

        # ── 2. admin-web rebuild ──
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

        # 验证 admin 套餐 API（公开 schema 通过 openapi 即可）
        print("\n--- 端点验证：openapi schema 含 membership ---")
        run(client,
            f"curl -ks '{BASE_URL}/api/openapi.json' | "
            f"python3 -c 'import json,sys; d=json.load(sys.stdin); "
            "ps=[p for p in d[\"paths\"] if \"membership\" in p]; "
            "print(\"membership endpoints:\", len(ps)); "
            "[print(\" -\", x) for x in ps[:30]]' 2>&1 | tail -40",
            ignore_err=True)

        print("\nDEPLOY DONE.")
        print(f"Admin: {BASE_URL}/admin")
        print(f"Plans page: {BASE_URL}/admin/membership/plans")
    finally:
        client.close()


if __name__ == "__main__":
    main()
