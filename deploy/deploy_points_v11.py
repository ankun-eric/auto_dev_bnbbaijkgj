# -*- coding: utf-8 -*-
"""积分商城 v1.1 部署脚本：
- git pull 最新代码
- 重建后端（含新迁移脚本） + h5-web + admin-web
- 重启相关容器
- 最终 smoke 检查关键链接
"""
import sys
import time

from ssh_helper import create_client, run_cmd

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def step(title, cmd, ssh, timeout=1800):
    print("\n" + "=" * 80)
    print(f"[STEP] {title}")
    print(f"[CMD ] {cmd}")
    print("-" * 80)
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out:
        print(out[-8000:])
    if err:
        print(f"STDERR:\n{err[-2000:]}")
    print(f"[EXIT] {code}")
    return out, err, code


def main():
    ssh = create_client()
    try:
        step("git pull",
             f"cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline",
             ssh)
        step("backend build",
             f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -n 80",
             ssh, timeout=2400)
        step("h5-web build",
             f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 60",
             ssh, timeout=2400)
        step("admin-web build",
             f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -n 60",
             ssh, timeout=2400)
        step("up -d backend h5-web admin-web",
             f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web admin-web 2>&1 | tail -n 30",
             ssh)
        time.sleep(15)

        # smoke test - 覆盖 v1.1 核心链接
        smoke = (
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps && echo ---- && "
            f"curl -sS -o /dev/null -w 'backend-health: %{{http_code}}\\n' {BASE}/api/health -L && "
            f"curl -sS -o /dev/null -w 'user-mall-all: %{{http_code}}\\n' '{BASE}/api/points/mall?tab=all&page=1&page_size=20' -L && "
            f"curl -sS -o /dev/null -w 'user-mall-exchangeable: %{{http_code}}\\n' '{BASE}/api/points/mall?tab=exchangeable&page=1&page_size=20' -L && "
            f"curl -sS -o /dev/null -w 'h5-mall: %{{http_code}}\\n' {BASE}/points/mall -L && "
            f"curl -sS -o /dev/null -w 'h5-records: %{{http_code}}\\n' {BASE}/points/exchange-records -L && "
            f"curl -sS -o /dev/null -w 'admin-root: %{{http_code}}\\n' {BASE}/admin/ -L && "
            f"curl -sS -o /dev/null -w 'admin-login: %{{http_code}}\\n' {BASE}/admin/login -L"
        )
        step("smoke test", smoke, ssh)

        # 打印后端日志末尾 80 行（检查迁移脚本是否执行）
        step("backend logs tail",
             f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml logs backend --tail=80 2>&1",
             ssh)
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
