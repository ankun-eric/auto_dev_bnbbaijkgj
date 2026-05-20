"""[PRD-TCM-DRAWER-V12 2026-05-20] 体质测评 36 题 + 双触发 + AI 引用 部署脚本

改动范围：
- backend：
  - app/services/prd_tcm36_drawer_v12_migration.py（新增 seed + 5 字段 DDL）
  - app/services/tcm_context.py（新增）
  - app/api/chat_intent.py（新增 /api/chat/intent-detect 接口）
  - app/api/questionnaire.py（submit 返回 active_followup + 主体质）
  - app/models/models.py（ChatFunctionButton 5 新字段）
  - app/schemas/function_button.py（5 字段 Schema）
  - app/main.py（注册迁移 + 路由）
  - tests/test_tcm36_drawer_v12_20260520.py（8 个 TC）
- admin-web：
  - src/app/(admin)/function-buttons/page.tsx（5 个开关 UI）
- h5-web：
  - src/components/ai-chat/QuestionnairePreCard.tsx（新增）
  - src/app/(ai-chat)/ai-home/page.tsx（INLINE_CHAT/pre_card 渲染 + 意图识别拦截 + 主动追问）
"""
from __future__ import annotations

import os
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
    # backend - 新增/修改的源码
    ("backend/app/services/prd_tcm36_drawer_v12_migration.py",
     "backend/app/services/prd_tcm36_drawer_v12_migration.py"),
    ("backend/app/services/tcm_context.py",
     "backend/app/services/tcm_context.py"),
    ("backend/app/api/chat_intent.py",
     "backend/app/api/chat_intent.py"),
    ("backend/app/api/questionnaire.py",
     "backend/app/api/questionnaire.py"),
    ("backend/app/models/models.py",
     "backend/app/models/models.py"),
    ("backend/app/schemas/function_button.py",
     "backend/app/schemas/function_button.py"),
    ("backend/app/main.py",
     "backend/app/main.py"),
    # backend 测试
    ("backend/tests/test_tcm36_drawer_v12_20260520.py",
     "backend/tests/test_tcm36_drawer_v12_20260520.py"),
    # admin-web
    ("admin-web/src/app/(admin)/function-buttons/page.tsx",
     "admin-web/src/app/(admin)/function-buttons/page.tsx"),
    # h5-web
    ("h5-web/src/components/ai-chat/QuestionnairePreCard.tsx",
     "h5-web/src/components/ai-chat/QuestionnairePreCard.tsx"),
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

        # ── 1. backend：把改动的 .py 文件 docker cp 进容器并重启 ──
        print("\n--- docker cp backend 文件到 backend 容器 ---")
        for local_rel, _ in FILES:
            if not local_rel.startswith("backend/app/"):
                continue
            host_abs = f"{PROJ_DIR}/{local_rel}"
            in_container = "/app/" + local_rel[len("backend/"):]
            run(client,
                f"docker cp '{host_abs}' '{backend_container}:{in_container}' 2>&1",
                ignore_err=True, show=False)

        # 拷贝测试文件进容器
        run(client,
            f"docker cp '{PROJ_DIR}/backend/tests/test_tcm36_drawer_v12_20260520.py' "
            f"'{backend_container}:/app/tests/test_tcm36_drawer_v12_20260520.py' 2>&1",
            ignore_err=True)

        print("\n--- 重启 backend 容器（触发启动迁移） ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} restart backend 2>&1 | tail -10",
            timeout=120, ignore_err=True)

        # 等待 backend 就绪
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

        # 抓启动日志，确认 seed 成功
        print("\n--- 抓 backend 启动日志，确认 seed ---")
        run(client,
            f"docker logs --tail 200 {backend_container} 2>&1 | grep -E 'tcm36|seed tcm_constitution' | tail -30",
            ignore_err=True)

        # ── 2. 数据库校验：tcm_constitution 36 题 ──
        print("\n--- DB 校验 questionnaire_question 题数 ---")
        run(client,
            f"docker exec {backend_container} python -c \""
            f"import asyncio; from sqlalchemy import text;"
            f"from app.core.database import async_session;"
            f"async def main():"
            f"    async with async_session() as db:"
            f"        r = await db.execute(text(\\\"SELECT count(*) FROM questionnaire_question q JOIN questionnaire_template t ON q.template_id = t.id WHERE t.code='tcm_constitution'\\\"));"
            f"        print('tcm_constitution question count:', r.scalar());"
            f"        r2 = await db.execute(text(\\\"SELECT sort_order FROM questionnaire_question q JOIN questionnaire_template t ON q.template_id = t.id WHERE t.code='tcm_constitution' ORDER BY sort_order DESC LIMIT 1\\\"));"
            f"        print('max sort_order:', r2.scalar());"
            f"asyncio.run(main())\" 2>&1 | tail -10",
            ignore_err=True)

        # ── 3. 重建 admin-web ──
        print("\n--- rebuild admin-web ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} stop admin-web 2>&1 | tail -3",
            ignore_err=True)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f admin-web 2>&1 | tail -3",
            ignore_err=True)
        print("Building admin-web (5-10 min)...")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} build admin-web 2>&1 | tail -100",
            timeout=1800)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d admin-web 2>&1 | tail -10")

        # ── 4. 重建 h5-web ──
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
                "docker inspect --format='{{.State.Status}}' " + h5_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 5}s] h5-web: {s}")
            if s == "running":
                rc2, out2, _ = run(
                    client,
                    f"docker logs --tail 60 {h5_container} 2>&1 | tail -30",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2 \
                        or "Listening on" in out2:
                    print("  h5-web ready.")
                    break
            time.sleep(5)

        # ── 5. smoke 测试 ──
        print("\n--- smoke 测试 ---")
        smoke_urls = [
            f"{BASE_URL}/api/openapi.json",
            f"{BASE_URL}/api/questionnaire/templates/by-code/tcm_constitution",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/",
        ]
        smoke_results = []
        for url in smoke_urls:
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  {url} -> {code}")
            smoke_results.append((url, code))

        # 实测 intent-detect 接口
        print("\n--- intent-detect smoke ---")
        run(client,
            f"curl -ks -X POST -H 'Content-Type: application/json' "
            f"-d '{{\"text\": \"我要做体质测评\"}}' "
            f"'{BASE_URL}/api/chat/intent-detect' 2>&1 | head -10",
            ignore_err=True)

        # ── 6. 远端 pytest（在 backend 容器内） ──
        print("\n--- backend 容器内 pytest 执行 ---")
        rc, out, _ = run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_tcm36_drawer_v12_20260520.py -v --tb=short --no-header 2>&1 | tail -120",
            ignore_err=True,
            timeout=300,
        )

        pytest_summary = ""
        for line in out.splitlines()[-15:]:
            if "passed" in line or "failed" in line or "error" in line.lower():
                pytest_summary = line.strip()

        print("\n========== 部署摘要 ==========")
        print(f"基础 URL: {BASE_URL}")
        print("smoke:")
        for u, c in smoke_results:
            print(f"  {c}  {u}")
        print(f"pytest: {pytest_summary or '(see above)'}")
        print("==============================")

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
