"""[PRD-MED-PLAN-V1 2026-05-16] 用药计划模块优化 部署脚本。

涉及：
- backend/app/models/models.py（MedicationReminder/ReminderSetting 新增字段）
- backend/app/services/schema_sync.py（自动迁移新字段）
- backend/app/api/health_plan_v2.py（同名去重 + 自动归档 + AI外呼标记）
- backend/app/api/prd469_health_v5.py（reminder-setting 增加字段；新增 medication-ai-call 路由 + 共管 入口）
- backend/app/schemas/health_plan_v2.py
- backend/tests/test_med_plan_v1_20260516.py
- h5-web/src/app/(ai-chat)/medication-plans/page.tsx（表单按 PRD 重写）
- h5-web/src/components/health-profile-v5/CareReminderBlock.tsx（AI 外呼开关）
"""
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY = "gateway"
GIT_BRANCH = "master"


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:])
    if show and err.strip():
        print("STDERR:", err[-1500:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")
    try:
        # 拉取最新代码
        run(client, f"cd {PROJ_DIR} && timeout 60 git fetch origin --depth 1 --no-tags 2>&1 | tail -10", timeout=90)
        run(client, f"cd {PROJ_DIR} && git reset --hard origin/{GIT_BRANCH} 2>&1 | tail -5")
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline")

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5-web"

        # 重建 backend
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop backend 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f backend 2>&1 | tail -3", ignore_err=True)
        print("Building backend (may take 2-4 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -40", timeout=900)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10")

        # 重建 h5-web
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (may take 3-6 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -40", timeout=1200)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10")

        # 等待 backend 健康
        print("\n--- Waiting for backend container ---")
        for i in range(48):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' "
                + backend_container + " 2>&1",
                ignore_err=True, show=False,
            )
            status = out.strip()
            print(f"  [{(i+1)*5}s] backend: {status}")
            running = status.startswith("running|")
            health = status.split("|", 1)[1] if "|" in status else ""
            if running and (health == "" or health == "healthy"):
                print("  backend ready.")
                break
            time.sleep(5)

        # 网关重连
        run(client, f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1", ignore_err=True)
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 状态汇总
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 容器内自检
        run(
            client,
            f"docker exec {backend_container} sh -c 'curl -sf http://localhost:8000/api/health || curl -sf http://localhost:8000/health' 2>&1 | head -c 500",
            ignore_err=True,
        )

        # 容器内跑本次新增测试
        print("\n--- Running new pytest inside backend container ---")
        run(
            client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_med_plan_v1_20260516.py -q --tb=short 2>&1 | tail -40'",
            ignore_err=True, timeout=300,
        )

        # 顺带跑健康档案 v2 + 用药提醒 旧用例（确保未回归）
        print("\n--- Running regression pytest inside backend container ---")
        run(
            client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_health_archive_bug_v2_20260516.py tests/test_prd439_medication_reminder.py -q --tb=line 2>&1 | tail -30'",
            ignore_err=True, timeout=600,
        )

        # 新接口存在性探活（应返回 401，证明路由已上线）
        print("\n--- Probe new endpoints via gateway ---")
        for path in [
            "api/health-plan/medications/list",
            "api/prd469/medication-ai-call",
            "api/prd469/care/medication-ai-call",
            "api/prd469/reminder-setting",
        ]:
            run(
                client,
                f"curl -s -o /dev/null -w 'HTTP_CODE=%{{http_code}} {path}\\n' "
                f"'http://localhost/autodev/{DEPLOY_ID}/{path}'",
                ignore_err=True,
            )
        # H5 用药计划页 200
        run(
            client,
            f"curl -s -o /dev/null -w 'HTTP_CODE=%{{http_code}}\\n' "
            f"'http://localhost/autodev/{DEPLOY_ID}/medication-plans'",
            ignore_err=True,
        )

        print("\n[DEPLOY DONE]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
