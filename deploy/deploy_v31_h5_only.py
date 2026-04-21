# -*- coding: utf-8 -*-
"""仅重新拉代码 + 重新构建 h5-web，然后重启 h5 容器。"""
import time
from ssh_helper import create_client, run_cmd

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def step(title, cmd, ssh, timeout=1500):
    print("\n" + "=" * 80)
    print(f"[STEP] {title}")
    print(f"[CMD ] {cmd}")
    print("-" * 80)
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out:
        print(out[-6000:])
    if err:
        print(f"STDERR:\n{err[-2000:]}")
    print(f"[EXIT] {code}")
    return out, err, code


def main():
    ssh = create_client()
    try:
        step("git pull", f"cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline", ssh)
        step(
            "build h5-web",
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 60",
            ssh,
            timeout=1500,
        )
        step(
            "up -d h5-web",
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -n 30",
            ssh,
        )
        time.sleep(10)
        step(
            "ps + smoke",
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps && echo ---- && "
            f"curl -sS -o /dev/null -w 'h5-home: %{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ -L && "
            f"curl -sS -o /dev/null -w 'h5-points-detail: %{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/points/detail -L && "
            f"curl -sS -o /dev/null -w 'h5-prod-detail: %{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/points/product-detail?id=1 -L && "
            f"curl -sS -o /dev/null -w 'backend: %{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health -L",
            ssh,
        )
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
