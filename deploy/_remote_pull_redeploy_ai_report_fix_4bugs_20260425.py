"""[2026-04-25] AI 报告解读链路 4 个 Bug 修复 - 远程 pull + 重建部署

通过 SSH 在服务器上执行 git pull，然后重建 backend 与 h5-web 容器，
最后将 gateway 加入项目网络并 reload。
所有产物都打印到 stdout，调用方负责落盘日志。
"""
from __future__ import annotations

import os
import sys
import time

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
NETWORK = f"{DEPLOY_ID}-network"
GATEWAY = "gateway-nginx"
COMPOSE_FILE = "docker-compose.prod.yml"
GIT_REPO_TOKEN_URL = (
    "https://ankun-eric:" + os.environ.get("GH_TOKEN", "REDACTED") +
    "@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    print(f"\n$ {cmd}", flush=True)
    _stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-5000:], flush=True)
    if err.strip():
        print("stderr:", err[-2500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def main() -> int:
    print(f"== SSH 连接 {USER}@{HOST}:{PORT} ==", flush=True)
    c = ssh()
    try:
        # Step A: 确认目录存在 + Git 远端配置 token
        run(c, f"ls -la {PROJECT_DIR} | head -5", timeout=15)

        # 设置远端 URL（带 token），保证 fetch 不需要交互
        run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_REPO_TOKEN_URL}", timeout=15)

        # Step B: 拉取最新代码（GitHub 国内访问慢，允许较长超时）
        run(
            c,
            f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 360 git fetch origin master 2>&1 | tail -20",
            timeout=420,
        )
        run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master 2>&1 | tail -5", timeout=60)
        run(c, f"cd {PROJECT_DIR} && git clean -fd 2>&1 | tail -10", timeout=30)
        run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)

        # Step C: 重建 backend 与 h5-web 容器（使用 prod compose 文件）
        print("\n== 检查 compose 文件存在性 ==", flush=True)
        run(c, f"ls -la {PROJECT_DIR}/{COMPOSE_FILE}", timeout=10)

        print("\n== 重建 backend 镜像 ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache backend 2>&1 | tail -60",
            timeout=900,
        )

        print("\n== 重建 h5-web 镜像 ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache h5-web 2>&1 | tail -60",
            timeout=1200,
        )

        print("\n== 启动/更新 backend + h5-web ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend h5-web 2>&1 | tail -40",
            timeout=180,
        )

        # Step D: 等待 healthcheck（最多 120s）
        print("\n== 等待容器 healthy ==", flush=True)
        for i in range(24):
            code, out, _ = run(
                c,
                f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}",
                timeout=10,
            )
            lines = [ln for ln in out.splitlines() if ln.strip()]
            healthy_or_running = sum(
                1 for ln in lines if ("healthy" in ln) or ("Up" in ln and "unhealthy" not in ln and "starting" not in ln)
            )
            print(f"  [{i+1}/24] container_count={len(lines)} healthy/running={healthy_or_running}", flush=True)
            if lines and not any("starting" in ln or "unhealthy" in ln for ln in lines):
                if any("backend" in ln for ln in lines) and any("h5-web" in ln for ln in lines):
                    break
            time.sleep(5)

        # Step E: gateway 加入项目网络（防 down/up 后断开）+ reload
        print("\n== gateway 加入项目网络 ==", flush=True)
        run(c, f"docker network connect {NETWORK} {GATEWAY} 2>&1 || true", timeout=15)
        run(c, f"docker network inspect {NETWORK} --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'", timeout=10)
        run(c, f"docker exec {GATEWAY} nginx -t 2>&1", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1", timeout=15)

        # Step F: 内部健康探测
        print("\n== 服务器内部 curl 自检 ==", flush=True)
        run(
            c,
            f"curl -sk -o /dev/null -w 'h5=%{{http_code}}\\n' "
            f"https://localhost/autodev/{DEPLOY_ID}/",
            timeout=15,
        )
        run(
            c,
            f"curl -sk -o /dev/null -w 'checkup=%{{http_code}}\\n' "
            f"https://localhost/autodev/{DEPLOY_ID}/checkup",
            timeout=15,
        )
        run(
            c,
            f"curl -sk -o /dev/null -w 'login=%{{http_code}}\\n' "
            f"https://localhost/autodev/{DEPLOY_ID}/login",
            timeout=15,
        )
        run(
            c,
            f"curl -sk -o /dev/null -w 'api_captcha=%{{http_code}}\\n' "
            f"https://localhost/autodev/{DEPLOY_ID}/api/auth/captcha",
            timeout=15,
        )

        print("\n== 完成 ==", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
