"""[PRD-FAMILY-GUARDIAN-V1] 公众号推送·中转页（H5 alert-redirect）远程部署脚本。

执行：
  1. 远程 git fetch + reset --hard origin/master
  2. 写入 BUILD_COMMIT 到 .env
  3. 重新构建 backend 与 h5-web（--no-cache）
  4. 重启 backend + h5-web 容器
  5. 重连 gateway 网络 + reload
  6. 容器内运行 pytest test_alert_redirect.py
  7. 外部 curl 验证：
       - alert-redirect 页面可达（HTTP 200）
       - /api/alert/event 接口可达（POST 200/400）
       - /api/alert/click-tracking 接口可达（POST 404 表示路由已注册，逻辑可达）
"""
from __future__ import annotations

import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
import os

_GH_TOKEN = os.environ.get("GH_TOKEN", "<REDACTED_GH_TOKEN>")
GIT_URL = (
    f"https://ankun-eric:{_GH_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


def open_ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, 22, USER, PWD, look_for_keys=False, allow_agent=False, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, timeout: int = 900) -> tuple[int, str, str]:
    head = cmd if len(cmd) <= 280 else cmd[:280] + "..."
    print(f"\n$ {head}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-4500:])
    if err.strip():
        print("STDERR:", err[-1500:])
    print(f"[exit={code}]")
    return code, out, err


def main() -> None:
    cli = open_ssh()
    try:
        # 1) Sync code
        run(cli, f"cd {REMOTE_DIR} && git remote set-url origin '{GIT_URL}'")
        for attempt in range(3):
            code, _, _ = run(
                cli,
                f"cd {REMOTE_DIR} && timeout 90 git fetch origin master --no-tags 2>&1 | tail -10",
            )
            if code == 0:
                break
            time.sleep(5)
        run(cli, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        run(cli, f"cd {REMOTE_DIR} && git log -1 --oneline")

        # 2) Verify new files arrived on server
        run(cli, f"ls -la {REMOTE_DIR}/backend/app/utils/alert_sig.py")
        run(cli, f"ls -la {REMOTE_DIR}/backend/tests/test_alert_redirect.py")
        run(cli, f"ls -la {REMOTE_DIR}/h5-web/src/app/alert-redirect/page.tsx")

        # 3) BUILD_COMMIT
        run(
            cli,
            f"cd {REMOTE_DIR} && BC=$(git log -1 --format='%H') && echo \"BUILD_COMMIT=$BC\" > .env.build "
            "&& (grep -v '^BUILD_COMMIT=' .env > .env.tmp 2>/dev/null || true) "
            "&& cat .env.build >> .env.tmp && mv .env.tmp .env && tail -3 .env",
        )

        # 4) Rebuild backend & h5-web
        run(
            cli,
            f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -10",
            timeout=1500,
        )
        run(
            cli,
            f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -10",
            timeout=1800,
        )

        # 5) Restart containers
        run(
            cli,
            f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend h5-web 2>&1 | tail -10",
        )
        run(cli, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")

        # 6) Wait for healthy
        time.sleep(12)
        run(
            cli,
            f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep -E '{DEPLOY_ID}|gateway'",
        )

        # 7) Run pytest in backend container
        run(
            cli,
            f"docker exec {DEPLOY_ID}-backend python -m pytest tests/test_alert_redirect.py -v 2>&1 | tail -30",
            timeout=300,
        )

        # 8) Reload gateway + SSL check
        run(cli, "docker exec gateway nginx -t 2>&1")
        run(cli, "docker exec gateway nginx -s reload 2>&1")
        time.sleep(2)

        # 9) External smoke tests
        print("\n========== External smoke tests ==========")
        run(cli, f"curl -Is '{BASE_URL}/alert-redirect/' 2>&1 | head -5")
        run(
            cli,
            f"curl -s -o /dev/null -w 'HTTP=%{{http_code}}\\n' "
            f"-X POST '{BASE_URL}/api/alert/event' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"event\":\"alert_redirect_view\"}}'",
        )
        run(
            cli,
            f"curl -s -o /dev/null -w 'HTTP=%{{http_code}}\\n' "
            f"-X POST '{BASE_URL}/api/alert/event' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"event\":\"unknown_event\"}}'",
        )
        run(
            cli,
            f"curl -s -o /dev/null -w 'HTTP=%{{http_code}}\\n' "
            f"-X POST '{BASE_URL}/api/alert/click-tracking' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"logId\":99999999}}'",
        )
    finally:
        cli.close()


if __name__ == "__main__":
    main()
