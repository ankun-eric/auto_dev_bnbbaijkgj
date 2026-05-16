"""[BUG_FIX_用药识别千图一答 2026-05-16] 部署脚本

本次只改动了后端：
- backend/app/services/ai_service.py（多模态升级）
- backend/app/api/drug.py（视觉真识别 + identify-v2）
- backend/scripts/cleanup_legacy_drug_identify.py（脏数据清理脚本）
- backend/tests/test_drug_identify_vlm_20260516.py（回归测试）

所以只需要重建 backend 容器，不需要重建 h5-web / admin-web。
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
        # 1. 同步代码
        run(
            client,
            f"cd {PROJ_DIR} && timeout 60 git fetch origin --depth 1 --no-tags 2>&1 | tail -10",
            timeout=90,
        )
        run(client, f"cd {PROJ_DIR} && git reset --hard origin/{GIT_BRANCH} 2>&1 | tail -5")
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline")

        # 2. 准备 BUILD_INFO（保持与其它部署脚本同样的语义）
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

        # 3. 重建 backend 容器（代码改动）
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

        print("Building backend with --no-cache (may take 2-4 minutes)...")
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache {SERVICE} 2>&1 | tail -60",
            timeout=900,
        )

        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d {SERVICE} 2>&1 | tail -10",
        )

        # 4. 等待容器就绪
        print("\n--- Waiting for backend container to be running ---")
        for i in range(36):  # 最长 180s
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
            running = status.startswith("running|")
            health = status.split("|", 1)[1] if "|" in status else ""
            if running and (health == "" or health == "healthy"):
                print("  backend is ready.")
                break
            if "unhealthy" in status:
                print("  WARNING: backend reported unhealthy")
            time.sleep(5)

        # 5. 确保 gateway 接入 backend 网络
        run(
            client,
            f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1",
            ignore_err=True,
        )
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(
            client,
            f"docker exec {GATEWAY} nginx -s reload 2>&1",
            ignore_err=True,
        )

        # 6. 状态展示
        print("\n--- Final container status ---")
        run(
            client,
            f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
        )

        # 7. 容器内自检 + 路由探活
        run(
            client,
            f"docker exec {CONTAINER} sh -c 'curl -sf http://localhost:8000/api/health || curl -sf http://localhost:8000/health' 2>&1 | head -c 500",
            ignore_err=True,
        )

        # 8. 运行后端容器内的本次 Bug 修复 pytest（直接打镜像里的 source）
        print("\n--- Running pytest inside backend container ---")
        run(
            client,
            f"docker exec {CONTAINER} sh -c 'cd /app && python -m pytest tests/test_drug_identify_vlm_20260516.py -q --tb=short 2>&1 | tail -40'",
            ignore_err=True,
            timeout=300,
        )

        print("\n[DEPLOY DONE]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
