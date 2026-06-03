"""[守护人体系 PRD v1.2] 部署修复：rebuild backend 镜像"""
from __future__ import annotations
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def ssh_run(client, cmd, timeout=600):
    print(f"[ssh] $ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = out + ("\n[stderr]\n" + err if err.strip() else "")
    tail = "\n".join(combined.splitlines()[-60:])
    print(tail)
    print(f"[ssh] exit={rc}")
    return rc, combined


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        print("\n[1] Rebuild backend 镜像")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build backend 2>&1 | tail -10",
            timeout=600,
        )
        print("\n[2] up -d backend（不重启 db）")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose up -d backend 2>&1 | tail -10",
            timeout=120,
        )

        print("\n[3] 等待 backend 启动 + schema 迁移完成")
        for i in range(45):
            time.sleep(2)
            rc, out = ssh_run(
                client,
                f"docker logs --tail=80 {DEPLOY_ID}-backend 2>&1 | tail -40",
                timeout=20,
            )
            if "Application startup complete" in out or "Uvicorn running" in out:
                print(f"    backend ready @ {(i + 1) * 2}s")
                break

        print("\n[4] 验证 schema 已迁移")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health -e \""
            f"SHOW COLUMNS FROM membership_plans LIKE 'max_managed'; "
            f"SHOW COLUMNS FROM membership_plans LIKE 'emergency_ai_call_count'; "
            f"SHOW TABLES LIKE 'emergency_call_sources'; "
            f"SHOW TABLES LIKE 'guardian_proxy_pay'; "
            f"SHOW TABLES LIKE 'ai_call_reminders'; "
            f"SELECT COUNT(*) AS builtin_count FROM emergency_call_sources WHERE is_builtin=1;\" 2>&1",
            timeout=60,
        )

        print("\n[5] HTTP smoke")
        # 用 -L 跟随重定向；查询关键端点存在
        for path in [
            "/api/openapi.json",
            "/api/guardian/v12/i-guard",
            "/api/guardian/v12/managed-quota-summary",
            "/api/admin/emergency-sources",
        ]:
            ssh_run(
                client,
                f"curl -sk -o /tmp/resp.txt -w '{path} → %{{http_code}}\\n' '{BASE_URL}{path}'; "
                f"head -c 300 /tmp/resp.txt; echo",
                timeout=15,
            )

        print("\n[6] 服务器内单元测试")
        # 先安装 pytest
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend pip install pytest pytest-asyncio httpx aiosqlite -q 2>&1 | tail -5",
            timeout=120,
        )
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_guardian_system_v12.py -v 2>&1 | tail -30'",
            timeout=300,
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
