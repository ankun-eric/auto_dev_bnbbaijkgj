"""[Bug-367 客户端订单顾客操作鉴权误判 v1.0] 远程部署脚本

通过 SSH 让远程服务器从 GitHub 拉取最新 master 并重建 backend 镜像，
然后跑 health 检查 + 容器内 pytest 验证 require_customer_client_session 已生效。
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh_run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[stderr]\n{err}")
    print(f"[exit={code}]")
    return code, out, err


def main() -> int:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting {USER}@{HOST} ...")
    cli.connect(HOST, username=USER, password=PASS, timeout=30)

    try:
        print("\n========== 1. git pull origin master (with retry) ==========")
        ssh_run(
            cli,
            f"cd {PROJECT_DIR} && git config --global --add safe.directory {PROJECT_DIR} && "
            "for i in 1 2 3 4 5; do echo \"[try $i] git fetch ...\"; "
            "if timeout 120 git fetch origin master; then echo OK; break; fi; "
            "sleep 10; done && git reset --hard origin/master && git log -1 --oneline",
            timeout=900,
        )

        print("\n========== 2. docker compose build & restart backend ==========")
        ssh_run(
            cli,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -25 && "
            "docker compose -f docker-compose.prod.yml up -d --no-deps backend 2>&1 | tail -10",
            timeout=900,
        )

        print("\n========== 3. wait backend healthy ==========")
        time.sleep(10)
        for i in range(8):
            code, out, _ = ssh_run(
                cli,
                f"curl -s -o /dev/null -w '%{{http_code}}' '{BASE_URL}/api/health'",
            )
            print(f"  health probe {i+1}: {out.strip()}")
            if out.strip() == "200":
                break
            time.sleep(5)

        print("\n========== 4. verify code in container ==========")
        ssh_run(
            cli,
            f"BC=$(docker ps -qf 'name={DEPLOY_ID}.*backend') && "
            "docker exec $BC grep -nE 'require_customer_client_session|CUSTOMER_FORBIDDEN_DETAIL|CLIENT_H5_USER' "
            "/app/app/utils/client_source.py | head -20 && "
            "echo '---' && "
            "docker exec $BC grep -nE 'require_customer_client_session' /app/app/api/unified_orders.py | head -20",
        )

        print("\n========== 5. run targeted pytest in container (non-UI auto test) ==========")
        code, out, err = ssh_run(
            cli,
            f"BC=$(docker ps -qf 'name={DEPLOY_ID}.*backend') && "
            "docker exec $BC python -m pytest "
            "tests/test_bugfix_customer_client_session_v1.py "
            "tests/test_prd05_verify_lockdown_v1.py "
            "tests/test_prd03_reschedule_v1.py "
            "tests/test_modify_appointment_bugfix.py "
            "tests/test_orders_status_v2.py "
            "tests/test_orders_aftersales_v3.py "
            "tests/test_h5_pay_link_bugfix.py "
            "tests/test_h5_pay_success_bugfix.py "
            "tests/test_on_site_fulfillment_v1.py "
            "--tb=short -q 2>&1 | tail -40",
            timeout=900,
        )

        print("\n========== 6. full backend pytest collection sanity check ==========")
        ssh_run(
            cli,
            f"BC=$(docker ps -qf 'name={DEPLOY_ID}.*backend') && "
            "docker exec $BC python -m pytest tests/ --collect-only -q 2>&1 | tail -5",
        )

        print("\n========== 7. container list ==========")
        ssh_run(
            cli,
            f"docker ps --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
        )

        print("\n[DONE]")
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
