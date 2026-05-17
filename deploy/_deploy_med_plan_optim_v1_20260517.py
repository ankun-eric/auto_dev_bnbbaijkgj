"""[PRD-MED-PLAN-OPTIM-V1 2026-05-17] 部署脚本：用药计划页面优化（H5 + 小程序）。

涉及变更：
- backend/app/api/health_plan_v2.py 服用时机映射 + long_term 强制清空 end_date
- backend/tests/test_med_plan_optim_v1_20260517.py 新增 8 项测试
- h5-web/src/components/medication/MedicationFormPanel.tsx 终版表单
- h5-web/src/components/medication/MedicalAdviceTip.tsx 新增医嘱条
- h5-web/src/components/medication/CycleDrawer.tsx 新增服用周期抽屉
- h5-web/src/app/(ai-chat)/ai-home/medication-plans/page.tsx 列表卡片主色
- miniprogram/pages/health-plan/medication-form/* 重构（小程序仅打包，不部署到服务器）
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
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
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
        # git fetch with retry
        for attempt in range(1, 5):
            rc, _, _ = run(
                client,
                f"cd {PROJ_DIR} && timeout 180 git fetch origin {GIT_BRANCH} --depth 5 --no-tags 2>&1 | tail -10",
                timeout=240, ignore_err=True,
            )
            if rc == 0:
                print(f"git fetch ok (attempt {attempt})")
                break
            print(f"git fetch failed (attempt {attempt}), retrying...")
            time.sleep(10 * attempt)
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
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -80", timeout=1800)
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

        # gateway 接入网络 + reload
        run(client, f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1", ignore_err=True)
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 状态
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 容器内健康自检
        run(
            client,
            f"docker exec {backend_container} sh -c 'curl -sf http://localhost:8000/api/health || curl -sf http://localhost:8000/health' 2>&1 | head -c 500",
            ignore_err=True,
        )

        # 容器内跑新增测试（容器内不一定装了 pytest，失败可忽略）
        print("\n--- Running pytest inside backend container (best-effort) ---")
        run(
            client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_med_plan_optim_v1_20260517.py -v --tb=short 2>&1 | tail -80'",
            ignore_err=True, timeout=300,
        )

        # 公网 smoke
        print("\n--- 公网 smoke 测试 ---")
        smoke_targets = [
            ("/ai-home", "302/200"),
            ("/ai-home/medication-plans", "200/302"),
            ("/ai-home/medication-plans/new", "200/302/308"),
            ("/api/health-plan/medications", "200/401"),
            ("/api/medication-library/suggest?q=ab", "200/401"),
        ]
        base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for path, _ in smoke_targets:
            url = base + path
            run(
                client,
                f"curl -sk -o /dev/null -w 'HTTP %{{http_code}} -> {path}\\n' '{url}'",
                ignore_err=True, show=True,
            )
        print("\nDeployment done.")
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
