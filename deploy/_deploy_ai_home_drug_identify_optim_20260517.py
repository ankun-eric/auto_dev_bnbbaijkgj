"""[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 部署脚本：ai-home 用药识别优化。

涉及变更：
- backend/app/api/chat.py（时区修复 + mark-added-to-plan 接口）
- backend/app/schemas/chat.py（datetime 字段加 UTC 后缀序列化器）
- backend/app/schemas/ai_home_config.py（idle_timeout_minutes 30→60）
- backend/app/services/drug_identify_engine.py（两段播报流式 + 个性化风险）
- backend/app/utils/datetime_utils.py（新增统一时区工具）
- backend/tests/test_ai_home_drug_identify_optim_20260517.py（新增 9 项测试）
- h5-web ai-home/page.tsx（流式接收 + drugMeta 还原 + mark-added-to-plan）
- h5-web ai-home/components/DrugIdentifyCard.tsx（4 模块 + 按钮固底 + 已加入态）
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
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -80", timeout=1500)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10")

        # 等待 backend 健康
        print("\n--- Waiting for backend container ---")
        for i in range(40):
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

        # 容器内跑新增测试
        print("\n--- Running pytest inside backend container ---")
        run(
            client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_ai_home_drug_identify_optim_20260517.py -v --tb=short 2>&1 | tail -80'",
            ignore_err=True, timeout=300,
        )

        # gateway 公开路由探活
        print("\n--- Probe public URLs via gateway ---")
        base = f"http://localhost/autodev/{DEPLOY_ID}"
        probes = [
            f"{base}/",
            f"{base}/ai-home",
            f"{base}/health-profile",
            f"{base}/api/chat/sessions",
        ]
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
