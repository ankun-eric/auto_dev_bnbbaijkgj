"""
部署脚本：将本次 5 项 Bug 修复部署到服务器 h5 容器
- 在服务器拉取最新 master
- 仅重建 h5-web 服务 (无需 --no-cache 全量，但用 build 触发新的源码进入 image)
- 等待 h5 容器健康
- 通过外部 HTTPS 检查 AI 首页可达
"""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
H5_CONTAINER = f"{DEPLOY_ID}-h5"


def run(client, cmd, timeout=600, label=None):
    label = label or cmd[:80]
    print(f"\n>>> {label}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode(errors="ignore")
    err = stderr.read().decode(errors="ignore")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip())
    if err:
        print("STDERR:", err.rstrip())
    print(f"--- exit={rc}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PWD, timeout=30,
                   look_for_keys=False, allow_agent=False)

    try:
        # 1. 拉最新代码（reset --hard 完全覆盖本地）
        run(client, f"cd {PROJ_DIR} && git fetch origin master --depth 50 2>&1 | tail -20",
            label="git fetch master")
        run(client, f"cd {PROJ_DIR} && git reset --hard origin/master 2>&1 | tail -5",
            label="git reset --hard origin/master")
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline", label="latest commit")

        # 2. 重建 h5-web 容器（仅此服务，不动 backend/admin/db）
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -40",
            timeout=900, label="docker compose build h5-web --no-cache")

        # 3. 重启 h5-web
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -20",
            label="docker compose up -d h5-web")

        # 4. 等待容器健康
        for i in range(24):
            rc, out, _ = run(client,
                             f"docker inspect -f '{{{{.State.Health.Status}}}}' {H5_CONTAINER} 2>/dev/null || docker inspect -f '{{{{.State.Status}}}}' {H5_CONTAINER}",
                             label=f"check h5 status [{i+1}/24]")
            status = out.strip()
            if status in ("healthy", "running"):
                # 再检查具体的 healthy
                if status == "healthy" or i >= 6:
                    print(f"h5 container is {status}")
                    break
            time.sleep(5)

        # 5. 确认 gateway 网络
        run(client, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || true",
            label="ensure gateway in network")
        run(client, f"docker exec gateway-nginx nginx -s reload 2>&1 || true",
            label="gateway reload")

        # 6. 验证 BUILD info 与文件
        run(client, f"docker exec {H5_CONTAINER} cat /app/BUILD_INFO 2>/dev/null || echo 'no BUILD_INFO'",
            label="image BUILD_INFO")
        # 验证我们改动的代码在容器里（采样几个关键字）
        run(client, (
            f"docker exec {H5_CONTAINER} sh -c '"
            f"grep -c \"BUGFIX-AI-HOME-5ITEMS-V1\" .next/server/app/\\(ai-chat\\)/ai-home/page.js 2>/dev/null || true; "
            f"echo ---; "
            f"grep -ho \"权益升级\\|权益管理与升级\" .next/server/chunks/*.js 2>/dev/null | sort -u | head -5; "
            f"echo ---; "
            f"grep -c \"ai-home-more-icon-plus-circle\" .next/server/app/\\(ai-chat\\)/ai-home/page.js 2>/dev/null || true'"),
            label="sample code in container")

        # 7. 外部访问验证
        url_base = f"https://{HOST}/autodev/{DEPLOY_ID}"
        for path in ["/", "/ai-home", "/ai-home/medication-reminder"]:
            run(client, f"curl -sS -o /dev/null -w 'HTTP %{{http_code}} %{{size_download}}B in %{{time_total}}s URL=%{{url_effective}}\\n' '{url_base}{path}' --max-time 15",
                label=f"external check {path}")

    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
