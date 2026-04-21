# -*- coding: utf-8 -*-
"""
v3.1 发版：UI 与积分兑换优化 + 积分商城 Bug 修复

服务器部署操作：
1) git pull 最新代码
2) 重新构建后端 & admin-web & h5-web 镜像
3) 重启容器
4) 检查容器健康
5) 打印访问链接供后续全量链接检查
"""
import sys
import time
from ssh_helper import create_client, run_cmd

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def step(title, cmd, ssh, timeout=900):
    print("\n" + "=" * 80)
    print(f"[STEP] {title}")
    print(f"[CMD ] {cmd}")
    print("-" * 80)
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out:
        print(out[-4000:])
    if err:
        print(f"STDERR:\n{err[-2000:]}")
    print(f"[EXIT] {code}")
    return out, err, code


def main():
    ssh = create_client()
    try:
        # 1. git pull
        step("git fetch + reset --hard", f"cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline", ssh)

        # 2. docker compose build backend + frontends (admin-web, h5-web)
        step(
            "docker compose build backend",
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -n 40",
            ssh,
            timeout=1200,
        )
        step(
            "docker compose build admin-web",
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -n 40",
            ssh,
            timeout=1500,
        )
        step(
            "docker compose build h5-web",
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 40",
            ssh,
            timeout=1500,
        )

        # 3. up -d
        step(
            "docker compose up -d",
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1 | tail -n 40",
            ssh,
            timeout=300,
        )

        # 4. wait for health
        for i in range(24):
            out, _, _ = run_cmd(
                ssh,
                f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps",
                timeout=30,
            )
            print(f"[poll {i+1}/24]\n{out}")
            if "unhealthy" not in out and "starting" not in out and "Exit" not in out and "Restarting" not in out:
                # ensure all containers visible
                if "running" in out.lower() or " Up " in out:
                    break
            time.sleep(5)

        # 5. ensure gateway joined network
        step(
            "ensure gateway joined project network",
            f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || true",
            ssh,
        )

        # 6. quick smoke curl from server side
        step(
            "health smoke check (from server)",
            f"curl -sS -o /dev/null -w 'backend: %{{http_code}}\\n' http://localhost/autodev/{DEPLOY_ID}/api/health -k -L; "
            f"curl -sS -o /dev/null -w 'h5: %{{http_code}}\\n' http://localhost/autodev/{DEPLOY_ID}/ -k -L; "
            f"curl -sS -o /dev/null -w 'admin: %{{http_code}}\\n' http://localhost/autodev/{DEPLOY_ID}/admin/ -k -L",
            ssh,
        )
    finally:
        ssh.close()
    print("\nDEPLOY DONE")


if __name__ == "__main__":
    main()
