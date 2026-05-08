#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
[BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v2.0]
通过 SSH 在远程服务器上拉取最新代码并重建 H5 前端容器。

只重建 frontend 容器即可，因为本次修改只涉及 H5 顾客端 page.tsx。
"""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(client, cmd, timeout=600, check=True):
    print(f"\n>>> {cmd}")
    sys.stdout.flush()
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}", file=sys.stderr)
    print(f"[exit={rc}]")
    sys.stdout.flush()
    if check and rc != 0:
        raise RuntimeError(f"command failed (rc={rc}): {cmd}")
    return rc, out, err


def main():
    print(f"[INFO] connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    print("[INFO] connected.")

    try:
        # 1. 检查项目目录
        run(client, f"ls -la {PROJECT_DIR} | head -30")

        # 2. git pull 最新代码
        run(client, f"cd {PROJECT_DIR} && git fetch --all && git reset --hard origin/master && git log --oneline -5", timeout=180)

        # 3. 验证修改已到达
        rc, out, err = run(
            client,
            f"cd {PROJECT_DIR} && grep -n 'BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v2.0' h5-web/src/app/unified-order/\\[id\\]/page.tsx | head -5",
            check=False,
        )
        if rc != 0 or "v2.0" not in out:
            raise RuntimeError("代码没有同步到服务器，未找到 v2.0 标记")

        # 4. 列出当前容器
        run(client, "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}' | head -30", check=False)

        # 5. 重新构建并启动 H5 frontend 容器
        # 先看 docker-compose 文件
        run(client, f"ls {PROJECT_DIR}/docker-compose*.yml 2>/dev/null || echo no-compose-file", check=False)

        # 使用工程内的 docker compose 重新构建 frontend
        run(
            client,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.yml build h5-web 2>&1 | tail -50",
            timeout=900,
            check=False,
        )

        # 重启 h5-web 容器
        run(
            client,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.yml up -d h5-web 2>&1 | tail -20",
            timeout=300,
            check=False,
        )

        # 6. 检查容器状态
        time.sleep(5)
        run(client, f"docker ps --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'", check=False)

        # 7. curl 测试 h5 入口
        run(
            client,
            f"curl -sk -o /dev/null -w 'HTTP=%{{http_code}}\\n' https://{HOST}/autodev/{DEPLOY_ID}/",
            check=False,
        )
        run(
            client,
            f"curl -sk -o /dev/null -w 'HTTP=%{{http_code}}\\n' https://{HOST}/autodev/{DEPLOY_ID}/unified-orders",
            check=False,
        )

        print("\n[INFO] deployment completed.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
