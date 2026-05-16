"""绕过 git，直接 scp 把本次修复的关键文件上传服务器并重建 h5-web。"""
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY = "gateway"

# 所有需要上传/同步的本地文件 -> 服务器路径
FILES = [
    # backend 新增
    ("backend/app/api/medication_plans_v1.py", "backend/app/api/medication_plans_v1.py"),
    ("backend/app/services/medication_status_scheduler.py", "backend/app/services/medication_status_scheduler.py"),
    ("backend/tests/test_med_plan_entry_v1_20260517.py", "backend/tests/test_med_plan_entry_v1_20260517.py"),
    # backend 修改
    ("backend/app/api/health_plan_v2.py", "backend/app/api/health_plan_v2.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    # h5-web 新增路由
    ("h5-web/src/app/(ai-chat)/ai-home/medication-reminder/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/medication-reminder/page.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/medication-plans/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/medication-plans/page.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/medication-plans/new/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/medication-plans/new/page.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/medication-plans/[id]/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/medication-plans/[id]/page.tsx"),
    # h5-web 公共组件
    ("h5-web/src/components/medication/MedicationFormPanel.tsx",
     "h5-web/src/components/medication/MedicationFormPanel.tsx"),
    # h5-web 修改的页面
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx", "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/components/AddMedicationDrawer.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/components/AddMedicationDrawer.tsx"),
    ("h5-web/src/app/chat/[sessionId]/page.tsx", "h5-web/src/app/chat/[sessionId]/page.tsx"),
    ("h5-web/src/app/health-profile/page.tsx", "h5-web/src/app/health-profile/page.tsx"),
]

# 需要从服务器删除的旧路由
DELETE_PATHS = [
    f"{PROJ_DIR}/h5-web/src/app/(ai-chat)/medication-plans/page.tsx",
    f"{PROJ_DIR}/h5-web/src/app/health-plan/medications/add/page.tsx",
    f"{PROJ_DIR}/h5-web/src/app/health-plan/medications/page.tsx",
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-2500:])
    if show and err.strip():
        print("STDERR:", err[-800:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:200]}\n{err}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")
    try:
        sftp = client.open_sftp()
        # 上传所有需要同步的文件
        print(f"\n--- Uploading {len(FILES)} files via SFTP ---")
        for local, remote in FILES:
            remote_full = f"{PROJ_DIR}/{remote}"
            remote_dir = "/".join(remote_full.split("/")[:-1])
            run(client, f"mkdir -p '{remote_dir}'", show=False)
            try:
                sftp.put(local, remote_full)
                print(f"  ✓ {local} -> {remote_full}")
            except Exception as ex:
                print(f"  ✗ {local}: {ex}")
                raise
        # 删除旧路由
        print(f"\n--- Deleting {len(DELETE_PATHS)} legacy paths ---")
        for p in DELETE_PATHS:
            run(client, f"rm -f '{p}' && echo deleted: {p}", ignore_err=True, show=False)
            print(f"  ✗ {p}")
        sftp.close()

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5-web"

        # 重建 backend（代码已变）
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop backend 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f backend 2>&1 | tail -3", ignore_err=True)
        print("Building backend...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -30", timeout=900)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10")

        # 重建 h5-web
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (may take 3-6 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -80", timeout=1500)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10")

        # 等待 backend ready
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

        # gateway reload
        run(client, f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1", ignore_err=True)
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 容器内跑测试
        print("\n--- Running pytest inside backend container ---")
        run(client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pip install pytest pytest-asyncio httpx -q 2>&1 | tail -3'",
            ignore_err=True, timeout=180)
        run(client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_med_plan_entry_v1_20260517.py -v --tb=short 2>&1 | tail -60'",
            ignore_err=True, timeout=300)
        # 回归测试
        run(client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_med_plan_v1_20260516.py -q --tb=short 2>&1 | tail -20'",
            ignore_err=True, timeout=300)

        # 公开路由探活
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
        probe_cmd = " ; ".join(
            f"curl -sL -o /dev/null -w '%{{http_code}}  {u}\\n' '{u}'"
            for u in probes
        )
        run(client, probe_cmd, ignore_err=True)

        print("\n[DEPLOY DONE]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
