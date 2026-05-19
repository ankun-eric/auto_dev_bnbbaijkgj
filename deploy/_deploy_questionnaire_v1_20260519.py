"""[PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
通用问卷与图像采集架构重构 部署脚本。

改动范围：
- 后端
  - backend/app/models/models.py：ChatFunctionButton 加 3 字段 + 新增 5 张 questionnaire_* 表
  - backend/app/schemas/function_button.py：AI 子类型新增 questionnaire/image_capture；新增 NEW_AI_FUNCTION_TYPES / ALLOWED_CAPTURE_PURPOSES
  - backend/app/schemas/questionnaire.py：通用问卷 Schema
  - backend/app/api/function_button.py：新校验 _validate_questionnaire_and_capture
  - backend/app/api/questionnaire.py：通用问卷 API（用户端 + 管理端）
  - backend/app/services/prd_questionnaire_v1_migration.py：数据迁移
  - backend/app/main.py：路由挂载 + 启动期迁移调用
  - backend/tests/test_questionnaire_v1_20260519.py：7 用例
- admin-web
  - admin-web/src/app/(admin)/function-buttons/page.tsx：子类型升级为 5 项 + 新字段表单
  - admin-web/src/app/(admin)/questionnaire-templates/page.tsx：新建通用问卷模板管理页
  - admin-web/src/app/(admin)/layout.tsx：菜单注册
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

FILES = [
    # 后端
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/schemas/function_button.py", "backend/app/schemas/function_button.py"),
    ("backend/app/schemas/questionnaire.py", "backend/app/schemas/questionnaire.py"),
    ("backend/app/api/function_button.py", "backend/app/api/function_button.py"),
    ("backend/app/api/questionnaire.py", "backend/app/api/questionnaire.py"),
    ("backend/app/services/prd_questionnaire_v1_migration.py",
     "backend/app/services/prd_questionnaire_v1_migration.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/tests/test_questionnaire_v1_20260519.py",
     "backend/tests/test_questionnaire_v1_20260519.py"),
    # admin-web
    ("admin-web/src/app/(admin)/function-buttons/page.tsx",
     "admin-web/src/app/(admin)/function-buttons/page.tsx"),
    ("admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
     "admin-web/src/app/(admin)/questionnaire-templates/page.tsx"),
    ("admin-web/src/app/(admin)/layout.tsx",
     "admin-web/src/app/(admin)/layout.tsx"),
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

        # backend 容器内同步代码 + 重启（依赖 lifespan 的 questionnaire_v1 迁移在启动期执行）
        print("\n--- 同步 backend 改动到容器 ---")
        backend_files = [
            ("backend/app/models/models.py", "/app/app/models/models.py"),
            ("backend/app/schemas/function_button.py", "/app/app/schemas/function_button.py"),
            ("backend/app/schemas/questionnaire.py", "/app/app/schemas/questionnaire.py"),
            ("backend/app/api/function_button.py", "/app/app/api/function_button.py"),
            ("backend/app/api/questionnaire.py", "/app/app/api/questionnaire.py"),
            ("backend/app/services/prd_questionnaire_v1_migration.py",
             "/app/app/services/prd_questionnaire_v1_migration.py"),
            ("backend/app/main.py", "/app/app/main.py"),
            ("backend/tests/test_questionnaire_v1_20260519.py",
             "/app/tests/test_questionnaire_v1_20260519.py"),
        ]
        for local_p, container_p in backend_files:
            # 先确保容器内目录存在
            run(client, f"docker exec {backend_container} mkdir -p $(dirname {container_p}) 2>&1",
                ignore_err=True, show=False)
            run(client, f"docker cp {PROJ_DIR}/{local_p} {backend_container}:{container_p} 2>&1",
                ignore_err=True, show=False)

        print("\n--- 重启 backend（触发 questionnaire_v1 迁移 + 5 张新表自动建表） ---")
        run(client, f"docker restart {backend_container} 2>&1 | tail -5",
            ignore_err=True, timeout=180)

        print("\n--- 等待 backend 就绪 ---")
        ready = False
        for i in range(80):
            rc, out, _ = run(
                client,
                "curl -ks -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/openapi.json || echo fail",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 3}s] backend openapi: {s}")
            if s == "200":
                ready = True
                break
            time.sleep(3)
        if not ready:
            print("WARN: backend not ready within timeout")

        # 检查迁移痕迹（数据库新表）
        print("\n--- 检查 questionnaire_template 表与 chat_function_buttons 新字段 ---")
        run(client,
            f"docker exec {backend_container} python -c "
            "\"from sqlalchemy import inspect, create_engine; "
            "import os; "
            "url = os.environ.get('DATABASE_URL', '').replace('+aiomysql', '+pymysql').replace('+asyncmy', '+pymysql'); "
            "e = create_engine(url); "
            "insp = inspect(e); "
            "tabs = insp.get_table_names(); "
            "print('has questionnaire_template:', 'questionnaire_template' in tabs); "
            "print('has questionnaire_question:', 'questionnaire_question' in tabs); "
            "print('has questionnaire_classification_rule:', 'questionnaire_classification_rule' in tabs); "
            "print('has questionnaire_recommendation:', 'questionnaire_recommendation' in tabs); "
            "print('has questionnaire_answer:', 'questionnaire_answer' in tabs); "
            "cols = [c['name'] for c in insp.get_columns('chat_function_buttons')]; "
            "print('btn has questionnaire_template_id:', 'questionnaire_template_id' in cols); "
            "print('btn has capture_purpose:', 'capture_purpose' in cols); "
            "print('btn has pre_card_enabled:', 'pre_card_enabled' in cols);\" 2>&1",
            ignore_err=True, timeout=120,
        )

        # rebuild admin-web
        print("\n--- rebuild admin-web ---")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} stop admin-web 2>&1 | tail -3",
            ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f admin-web 2>&1 | tail -3",
            ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} build admin-web 2>&1 | tail -120",
            timeout=1800)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d admin-web 2>&1 | tail -10")

        print("\n--- 等待 admin-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}' " + admin_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 5}s] admin-web: {s}")
            if s == "running":
                rc2, out2, _ = run(
                    client, f"docker logs --tail 40 {admin_container} 2>&1 | tail -25",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2:
                    break
            time.sleep(5)

        # smoke
        print("\n--- smoke ---")
        base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for url in [
            f"{base_url}/api/openapi.json",
            f"{base_url}/api/questionnaire/templates",
            f"{base_url}/admin/questionnaire-templates",
            f"{base_url}/admin/function-buttons",
        ]:
            rc, out, _ = run(client,
                             f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                             ignore_err=True, show=False)
            print(f"  {url} -> {out.strip()}")

        # 容器内 pytest（仅本次新增 + 关键回归）
        print("\n--- backend pytest（questionnaire_v1 新增 + function_button 回归） ---")
        run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_questionnaire_v1_20260519.py "
            f"-v --tb=short 2>&1 | tail -200",
            ignore_err=True,
            timeout=600,
        )

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
