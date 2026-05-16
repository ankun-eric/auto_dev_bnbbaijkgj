"""[PRD-MED-PLAN-ENTRY-V1 2026-05-17] 部署脚本：用药计划入口改造。

涉及变更：
- backend/app/api/medication_plans_v1.py（新增，6 个新接口）
- backend/app/services/medication_status_scheduler.py（新增，状态自动流转）
- backend/app/main.py（注册新路由）
- backend/app/api/health_plan_v2.py（list 接口新增 tab 过滤参数）
- backend/tests/test_med_plan_entry_v1_20260517.py（新增 16 项单元测试）
- h5-web ai-home 新增路由组：medication-reminder / medication-plans（list, new, [id]）
- h5-web 删除旧路由：(ai-chat)/medication-plans, health-plan/medications/*
- h5-web 修改 health-profile/page.tsx 摘要卡 + Hero 第 4 格
- h5-web 新增组件 components/medication/MedicationFormPanel.tsx
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
        run(client, f"cd {PROJ_DIR} && timeout 60 git fetch origin --depth 1 --no-tags 2>&1 | tail -10", timeout=90)
        run(client, f"cd {PROJ_DIR} && git reset --hard origin/{GIT_BRANCH} 2>&1 | tail -5")
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline")

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5-web"

        # 重建 backend
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop backend 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f backend 2>&1 | tail -3", ignore_err=True)
        print("Building backend (may take 2-4 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -40", timeout=900)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10")

        # 重建 h5-web
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (may take 3-6 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -60", timeout=1500)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10")

        # 等待 backend 健康
        print("\n--- Waiting for backend container ---")
        for i in range(40):
            rc, out, _ = run(client,
                "docker inspect --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' "
                + backend_container + " 2>&1", ignore_err=True, show=False)
            status = out.strip()
            print(f"  [{(i+1)*5}s] backend: {status}")
            running = status.startswith("running|")
            health = status.split("|", 1)[1] if "|" in status else ""
            if running and (health == "" or health == "healthy"):
                print("  backend ready.")
                break
            time.sleep(5)

        # gateway 接入网络 + reload
        run(client, f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1", ignore_err=True)
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 状态
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 容器内健康自检
        run(client,
            f"docker exec {backend_container} sh -c 'curl -sf http://localhost:8000/api/health || curl -sf http://localhost:8000/health' 2>&1 | head -c 500",
            ignore_err=True)

        # 容器内跑新增测试（核心质量门）
        print("\n--- Running pytest inside backend container ---")
        run(client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_med_plan_entry_v1_20260517.py -v --tb=short 2>&1 | tail -80'",
            ignore_err=True, timeout=300)

        # 回归 - 之前的 med-plan v1 测试也跑一下
        print("\n--- Regression: med-plan v1 (last week) ---")
        run(client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_med_plan_v1_20260516.py -q --tb=short 2>&1 | tail -30'",
            ignore_err=True, timeout=300)

        # gateway 公开路由探活
        print("\n--- Probe public URLs via gateway ---")
        base = f"http://localhost/autodev/{DEPLOY_ID}"
        probes = [
            f"{base}/",
            f"{base}/health-profile",
            f"{base}/ai-home/medication-reminder",
            f"{base}/ai-home/medication-plans",
            f"{base}/ai-home/medication-plans/new",
            f"{base}/api/medication-plans/hero-count",
            f"{base}/api/medication-plans/today",
            f"{base}/api/medication-plans/summary",
            f"{base}/api/medication-stats/monthly-compliance",
            f"{base}/api/health-plan/medications/list?tab=in_progress",
        ]
        for url in probes:
            run(client,
                f"curl -s -o /dev/null -w '{url}  ->  HTTP %{{http_code}}\\n' '{url}'",
                ignore_err=True, show=False)
            # 因为 show=False 没打印输出，手动 echo 一次
        # 用一行 shell 把所有 probe 串起来打印
        probe_cmd = " ; ".join(
            f"curl -s -o /dev/null -w '%{{http_code}}  {u}\\n' '{u}'"
            for u in probes
        )
        run(client, probe_cmd, ignore_err=True)

        print("\n[DEPLOY DONE]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
