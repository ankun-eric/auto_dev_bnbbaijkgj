"""
[PRD-健康档案路径统一 2026-05-16] 远程部署脚本 (修正版)

服务实际命名：db, backend, admin-web, h5
本次只改了 h5 端 (Next.js)，仅重建 h5 容器。
"""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD  = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY = "gateway"
GIT_BRANCH = "master"
SERVICE = "h5-web"
CONTAINER = f"{DEPLOY_ID}-h5"

def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
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
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")

    try:
        # 1. 同步代码（之前已 fetch + reset 到 7e32e47，这里二次确认）
        run(client, f"cd {PROJ_DIR} && timeout 60 git fetch origin --depth 1 --no-tags 2>&1 | tail -10", timeout=90)
        run(client, f"cd {PROJ_DIR} && git reset --hard origin/{GIT_BRANCH} 2>&1 | tail -5")
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline")

        # 2. 准备 BUILD_INFO
        run(client, f"cd {PROJ_DIR} && BUILD_COMMIT=$(git log -1 --format='%H') && echo \"BUILD_COMMIT=$BUILD_COMMIT\" > .env.build && sed -i '/^BUILD_COMMIT=/d' .env 2>/dev/null; echo \"BUILD_COMMIT=$BUILD_COMMIT\" >> .env && cat .env.build", ignore_err=True)

        # 3. 停止 + 删除 h5 容器
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop {SERVICE} 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f {SERVICE} 2>&1 | tail -3", ignore_err=True)

        # 4. 重建 h5 (--no-cache 确保最新代码)
        print("Building h5 with --no-cache (may take 3-6 minutes)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache {SERVICE} 2>&1 | tail -60", timeout=900)

        # 5. 启动 h5
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d {SERVICE} 2>&1 | tail -10")

        # 6. 等待容器就绪
        print("\n--- Waiting for h5 container to be running ---")
        for i in range(30):  # 最长 150s
            rc, out, _ = run(client, f"docker inspect --format='{{{{.State.Status}}}}|{{{{if .State.Health}}}}{{{{.State.Health.Status}}}}{{{{end}}}}' {CONTAINER} 2>&1", ignore_err=True, show=False)
            status = out.strip()
            print(f"  [{(i+1)*5}s] h5: {status}")
            running = status.startswith("running|")
            health = status.split("|", 1)[1] if "|" in status else ""
            if running and (health == "" or health == "healthy"):
                print("  h5 is ready.")
                break
            if "unhealthy" in status:
                print("  WARNING: h5 reported unhealthy")
            time.sleep(5)

        # 7. 重新连接 gateway 到网络
        run(client, f"docker network connect {DEPLOY_ID}-network {GATEWAY} 2>&1", ignore_err=True)

        # 8. gateway reload（路由无变化但 reload 保险）
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 9. 最终状态
        print("\n--- Final container status ---")
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 10. 容器内自检
        run(client, f"docker exec {CONTAINER} sh -c 'wget -qO- http://localhost:3000/ 2>/dev/null | head -c 200 || curl -sf http://localhost:3000/ | head -c 200'", ignore_err=True)

        print("\n[DEPLOY DONE]")
    finally:
        client.close()

if __name__ == "__main__":
    main()
