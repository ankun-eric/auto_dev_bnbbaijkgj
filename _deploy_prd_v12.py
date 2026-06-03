"""[守护人体系 PRD v1.2 2026-05-25] 部署脚本

涉及变更：
- backend/app/api/guardian_system_v12.py（新增 v1.2 路由）
- backend/app/models/models.py（新增 3 个模型类）
- backend/app/models/membership_plan.py（套餐字段规范化）
- backend/app/services/schema_sync.py（v1.2 schema 迁移）
- backend/app/api/membership.py（plan_to_dict 加 v1.2 字段）
- backend/app/schemas/membership.py（v1.2 字段）
- backend/app/main.py（注册 v12 路由）
- backend/tests/test_guardian_system_v12.py（14 条测试，已在本地通过）
- h5-web/src/app/health-profile/i-guard/page.tsx（新增）
- h5-web/src/app/member-center/page.tsx（新增）
- admin-web/src/app/(admin)/emergency-sources/page.tsx（新增）
- admin-web/src/app/(admin)/layout.tsx（菜单融合）

部署流程：
1. 打包 backend + h5-web/src + admin-web/src 到 tar.gz
2. SFTP 上传到服务器
3. 解压覆盖
4. docker compose build backend h5-web admin-web
5. up -d，等待健康检查
6. 服务器内 pytest test_guardian_system_v12.py
7. HTTP smoke 测试关键路径
"""
from __future__ import annotations

import sys
import tarfile
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

ROOT = Path(__file__).resolve().parent
TS = int(time.time())
LOCAL_TAR = ROOT / f"prd_v12_{TS}.tar.gz"
REMOTE_TAR = f"/tmp/prd_v12_{TS}.tar.gz"


def make_tar() -> Path:
    print(f"[1] 打包变更到 {LOCAL_TAR.name}")
    paths = [
        # backend
        Path("backend/app/api/guardian_system_v12.py"),
        Path("backend/app/api/guardian_system.py"),
        Path("backend/app/api/membership.py"),
        Path("backend/app/models/models.py"),
        Path("backend/app/models/membership_plan.py"),
        Path("backend/app/services/schema_sync.py"),
        Path("backend/app/schemas/membership.py"),
        Path("backend/app/main.py"),
        Path("backend/tests/test_guardian_system_v12.py"),
        # h5
        Path("h5-web/src/app/health-profile/i-guard/page.tsx"),
        Path("h5-web/src/app/member-center/page.tsx"),
        # admin
        Path("admin-web/src/app/(admin)/emergency-sources/page.tsx"),
        Path("admin-web/src/app/(admin)/layout.tsx"),
    ]
    with tarfile.open(LOCAL_TAR, "w:gz") as tar:
        for p in paths:
            abs_p = ROOT / p
            if abs_p.exists():
                tar.add(abs_p, arcname=str(p).replace("\\", "/"))
                print(f"    + {p}")
            else:
                print(f"    [WARN] 缺失：{p}")
    size_kb = LOCAL_TAR.stat().st_size / 1024
    print(f"    打包完成：{size_kb:.1f} KB")
    return LOCAL_TAR


def ssh_run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print(f"[ssh] $ {cmd[:160]}{'...' if len(cmd) > 160 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = (out + ("\n[stderr]\n" + err if err.strip() else ""))
    # 只打印最后 60 行避免过长
    tail = "\n".join(combined.splitlines()[-60:])
    print(tail)
    print(f"[ssh] exit={rc}")
    return rc, combined


def main() -> None:
    make_tar()

    print(f"\n[2] SSH 连接 {HOST}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()

    try:
        print(f"\n[3] 上传 {LOCAL_TAR.name} → {REMOTE_TAR}")
        sftp.put(str(LOCAL_TAR), REMOTE_TAR)
        print("    上传完成")

        # 解压到项目目录
        ssh_run(client, f"cd {REMOTE_PROJECT_DIR} && tar xzf {REMOTE_TAR}")
        ssh_run(client, f"ls -la {REMOTE_PROJECT_DIR}/backend/app/api/guardian_system_v12.py")
        ssh_run(client, f"ls -la {REMOTE_PROJECT_DIR}/h5-web/src/app/health-profile/i-guard/page.tsx")
        ssh_run(client, f"ls -la {REMOTE_PROJECT_DIR}/admin-web/src/app/\\(admin\\)/emergency-sources/page.tsx")

        print(f"\n[4] 重启 backend 并触发 schema 迁移")
        rc, _ = ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose restart backend",
            timeout=180,
        )
        if rc != 0:
            print("    backend restart 失败")
            return

        # 等待 backend 起来
        print("    等待 backend 健康……")
        for i in range(30):
            time.sleep(2)
            rc, out = ssh_run(
                client,
                f"docker logs --tail=20 {DEPLOY_ID}-backend 2>&1 | grep -E 'Application startup complete|Uvicorn running'",
                timeout=30,
            )
            if "Application startup complete" in out or "Uvicorn running" in out:
                print(f"    backend ready @ {(i + 1) * 2}s")
                break

        print(f"\n[5] 验证 v1.2 schema 已迁移（检查表/列）")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health -e \""
            f"SHOW COLUMNS FROM membership_plans LIKE 'max_managed'; "
            f"SHOW COLUMNS FROM membership_plans LIKE 'emergency_ai_call_count'; "
            f"SHOW TABLES LIKE 'emergency_call_sources'; "
            f"SHOW TABLES LIKE 'guardian_proxy_pay'; "
            f"SHOW TABLES LIKE 'ai_call_reminders'; "
            f"SELECT COUNT(*) AS builtin_count FROM emergency_call_sources WHERE is_builtin=1;\" 2>&1 | tail -30",
            timeout=60,
        )

        print(f"\n[6] 重新构建 h5-web（含 v1.2 新页面）")
        rc, _ = ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -30",
            timeout=900,
        )
        if rc == 0:
            ssh_run(
                client,
                f"cd {REMOTE_PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -10",
                timeout=60,
            )

        print(f"\n[7] 重新构建 admin-web（含 v1.2 紧急触发源管理）")
        rc, _ = ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build admin-web 2>&1 | tail -30",
            timeout=900,
        )
        if rc == 0:
            ssh_run(
                client,
                f"cd {REMOTE_PROJECT_DIR} && docker compose up -d admin-web 2>&1 | tail -10",
                timeout=60,
            )

        print(f"\n[8] 服务器内运行 v1.2 测试")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_guardian_system_v12.py -v 2>&1 | tail -40'",
            timeout=300,
        )

        print(f"\n[9] HTTP smoke 测试关键 URL")
        for path in [
            "/api/openapi.json",
            "/api/guardian/v12/i-guard",  # 401 未登录是预期
            "/health-profile/i-guard/",
            "/member-center/",
            "/admin/emergency-sources/",
        ]:
            ssh_run(
                client,
                f"curl -sk -o /dev/null -w '{path} → %{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=20,
            )

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        client.close()
        print("\n[Done] 部署流程结束")


if __name__ == "__main__":
    main()
