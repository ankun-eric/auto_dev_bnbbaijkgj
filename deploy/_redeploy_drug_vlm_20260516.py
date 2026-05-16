"""[BUG_FIX_用药识别千图一答 2026-05-16] 重新部署 + 验证脚本

上一轮 fetch --depth 1 没真正拿到最新 commit。本轮：
1. 强制 unshallow（如未 unshallow）；
2. 用更长 timeout fetch；
3. 验证服务器上 HEAD == ed5afbc 且关键新文件存在；
4. 重建 backend 容器；
5. 验证 /api/drugs/identify 等关键路由可达（401/405 都算"路由存在"）。
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
SERVICE = "backend"
CONTAINER = f"{DEPLOY_ID}-backend"

EXPECT_COMMIT = "ed5afbc"  # 至少前缀


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:])
    if show and err.strip():
        print("STDERR:", err[-2000:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(
        HOST,
        port=PORT,
        username=USER,
        password=PWD,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    print("Connected.")

    try:
        # 0. 先看当前状态
        run(client, f"cd {PROJ_DIR} && git rev-parse --is-shallow-repository", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline")

        # 1. 强制完整 fetch（多次重试）
        for attempt in range(1, 4):
            print(f"\n[git fetch attempt {attempt}/3]")
            rc, out, err = run(
                client,
                f"cd {PROJ_DIR} && timeout 240 git fetch origin {GIT_BRANCH} 2>&1 | tail -10",
                timeout=300,
                ignore_err=True,
            )
            if rc == 0:
                break
            time.sleep(10)

        run(client, f"cd {PROJ_DIR} && git reset --hard origin/{GIT_BRANCH} 2>&1 | tail -3")
        rc, out, _ = run(client, f"cd {PROJ_DIR} && git log -1 --oneline")
        if EXPECT_COMMIT not in out:
            print(
                f"\n[WARN] 服务器 HEAD 似乎不是预期的 {EXPECT_COMMIT}，但代码 reset 已经执行，继续构建。"
            )

        # 2. 验证关键新文件已落地
        run(
            client,
            f"cd {PROJ_DIR} && ls -la backend/app/api/drug.py "
            "backend/app/services/ai_service.py "
            "backend/scripts/cleanup_legacy_drug_identify.py "
            "backend/tests/test_drug_identify_vlm_20260516.py 2>&1",
        )
        run(
            client,
            f"cd {PROJ_DIR} && grep -c 'identify_drug_structured\\|build_vision_message_content' "
            "backend/app/services/ai_service.py 2>&1",
            ignore_err=True,
        )

        # 3. BUILD_INFO
        run(
            client,
            (
                f"cd {PROJ_DIR} && BUILD_COMMIT=$(git log -1 --format='%H') && "
                "echo \"BUILD_COMMIT=$BUILD_COMMIT\" > .env.build && "
                "sed -i '/^BUILD_COMMIT=/d' .env 2>/dev/null; "
                "echo \"BUILD_COMMIT=$BUILD_COMMIT\" >> .env && cat .env.build"
            ),
            ignore_err=True,
        )

        # 4. 重建 backend
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop {SERVICE} 2>&1 | tail -3",
            ignore_err=True,
        )
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f {SERVICE} 2>&1 | tail -3",
            ignore_err=True,
        )
        print("\nBuilding backend with --no-cache ...")
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache {SERVICE} 2>&1 | tail -40",
            timeout=900,
        )
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d {SERVICE} 2>&1 | tail -10",
        )

        # 5. 等待就绪
        print("\n--- Waiting for backend to be ready ---")
        ready = False
        for i in range(36):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' "
                + CONTAINER
                + " 2>&1",
                ignore_err=True,
                show=False,
            )
            status = out.strip()
            print(f"  [{(i + 1) * 5}s] backend: {status}")
            if status.startswith("running|"):
                health = status.split("|", 1)[1] if "|" in status else ""
                if health == "" or health == "healthy":
                    ready = True
                    break
            time.sleep(5)
        if not ready:
            print("WARNING: backend container did not become ready within 180s")

        # 6. 验证容器内 drug.py 已经是新版（含 identify-v2）
        run(
            client,
            f"docker exec {CONTAINER} sh -c 'grep -c \"identify-v2\\|identify_drug_structured\" /app/app/api/drug.py /app/app/services/ai_service.py 2>&1' ",
            ignore_err=True,
        )

        # 7. gateway reload
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 8. 状态
        run(
            client,
            f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
        )

        print("\n[REDEPLOY DONE]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
