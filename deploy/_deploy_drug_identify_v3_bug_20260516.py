"""[BUG_FIX_拍照识药三联_20260516] 部署脚本：拍照识药三联 Bug 修复 + 方案 E 聊天内嵌识药引擎。

涉及变更：
- backend/app/utils/ai_output_sanitizer.py（新增）
- backend/app/services/drug_identify_engine.py（新增）
- backend/app/services/health_profile_service.py（新增）
- backend/app/services/ai_service.py（OCR 优先 Prompt + sanitize + 一致性校验）
- backend/app/api/chat.py（聊天内嵌识药引擎路由 + family_member_id 透传 + 隐式上下文）
- backend/app/schemas/chat.py（ChatMessageCreate 新增 button_type / family_member_id 字段）
- backend/tests/test_drug_identify_bug_v3_20260516.py（新增 14 项单元测试）
- h5-web/src/app/(ai-chat)/ai-home/page.tsx（drugMeta 渲染 + family_member_id 透传 + retake 气泡）
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
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -40", timeout=900)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10")

        # 重建 h5-web
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (may take 3-6 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -40", timeout=1500)
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

        # gateway 接入网络
        run(client, f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1", ignore_err=True)
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 状态
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 容器内自检
        run(client,
            f"docker exec {backend_container} sh -c 'curl -sf http://localhost:8000/api/health || curl -sf http://localhost:8000/health' 2>&1 | head -c 500",
            ignore_err=True)

        # 容器内跑新增测试
        print("\n--- Running pytest inside backend container ---")
        run(client,
            f"docker exec {backend_container} sh -c 'cd /app && python -m pytest tests/test_drug_identify_bug_v3_20260516.py -q --tb=short 2>&1 | tail -40'",
            ignore_err=True, timeout=300)

        # 公开 ai-chat stream 路由探活（仅看 401/422 即可证明路由可达）
        print("\n--- Probe chat stream endpoint via gateway ---")
        run(client,
            f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' -X POST "
            f"-H 'Content-Type: application/json' -d '{{}}' "
            f"'http://localhost/autodev/{DEPLOY_ID}/api/chat/sessions/0/stream' 2>&1",
            ignore_err=True)

        print("\n[DEPLOY DONE]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
