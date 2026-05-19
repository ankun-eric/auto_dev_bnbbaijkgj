"""[PRD-LEGACY-HOME-CLEANUP-V1.1] 重建前端镜像（admin-web + h5-web）

第一次部署脚本使用 docker-compose 失败（服务器为 docker compose v2 plugin），
此脚本仅做前端镜像重建，使用 `docker compose`（带空格）命令。
"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(client, cmd, timeout=900, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-6000:], flush=True)
    if show and err.strip():
        print("STDERR:", err[-2000:], flush=True)
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
        # 确定 compose file
        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"
        print(f"compose file: {compose_file}")

        # 探测 docker compose 命令形式
        rc, out, _ = run(client, "docker compose version 2>&1 | head -1",
                         ignore_err=True, show=True)
        compose_cmd = "docker compose"
        if "Docker Compose" not in out and "docker compose" not in out.lower():
            rc, out, _ = run(client, "docker-compose --version 2>&1 | head -1",
                             ignore_err=True, show=True)
            compose_cmd = "docker-compose"

        print(f"\n--- 使用命令: {compose_cmd} ---")

        print("\n--- rebuild admin-web 与 h5-web (no-cache) ---")
        run(client,
            f"cd {PROJ_DIR} && {compose_cmd} -f {compose_file} build --no-cache admin-web h5-web 2>&1 | tail -80",
            ignore_err=False, timeout=1800)

        print("\n--- recreate admin-web 与 h5-web 容器 ---")
        run(client,
            f"cd {PROJ_DIR} && {compose_cmd} -f {compose_file} up -d --force-recreate admin-web h5-web 2>&1 | tail -30",
            ignore_err=False, timeout=300)

        # 等待就绪
        print("\n--- 等待 admin-web 和 h5-web 就绪 ---")
        for label, container in [("admin", f"{DEPLOY_ID}-admin"), ("h5", f"{DEPLOY_ID}-h5")]:
            for i in range(40):
                rc, out, _ = run(
                    client,
                    f"docker inspect -f '{{{{.State.Status}}}}' {container} 2>&1 || echo dead",
                    ignore_err=True, show=False,
                )
                s = out.strip()
                if s == "running":
                    print(f"  {label}: running")
                    break
                time.sleep(3)
            else:
                print(f"  {label}: NOT running after 120s")

        # 关键 URL 验证
        print("\n--- 验证前端 URL ---")
        base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for path, desc in [
            ("/admin/", "admin 首页"),
            ("/ai-home", "h5 ai-home"),
            ("/", "h5 root（应 302/200 跳 ai-home）"),
            ("/api/home-banners", "GET home-banners"),
            ("/api/app-settings/page-style", "GET page-style 常量"),
        ]:
            run(client,
                f"curl -ks -L -o /dev/null -w '{desc} ({path}): HTTP %{{http_code}}\\n' '{base_url}{path}'",
                ignore_err=True, show=True)

        print("\n✅ 前端重建完成")
    finally:
        client.close()


if __name__ == "__main__":
    main()
