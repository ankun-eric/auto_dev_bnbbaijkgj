"""[会员中心 PRD v1.0 终稿对齐 2026-05-26] 部署脚本

流程：
1. 上传修改/新增文件
2. rebuild backend + admin-web + h5-web
3. 重启容器（按依赖顺序）
4. 等待 backend 启动 + smoke 测试
5. 容器内运行新测试 test_member_center_prd_v1_aligned.py
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))


def ssh_run(client, cmd, timeout=600, silent=False):
    if not silent:
        print(f"[ssh] $ {cmd[:240]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = out + ("\n[stderr]\n" + err if err.strip() else "")
    if not silent:
        tail = "\n".join(combined.splitlines()[-80:])
        print(tail)
        print(f"[ssh] exit={rc}")
    return rc, combined


def scp_put(sftp, local_path, remote_path):
    print(f"[scp] {local_path} → {remote_path}")
    sftp.put(local_path, remote_path)


FILES = [
    # 后端
    "backend/app/models/membership_plan.py",
    "backend/app/schemas/membership.py",
    "backend/app/api/membership.py",
    "backend/app/api/member_center_v2.py",
    "backend/app/api/product_admin.py",
    "backend/app/api/unified_orders.py",
    "backend/app/api/guardian_system_v12.py",
    "backend/app/schemas/unified_orders.py",
    "backend/app/services/schema_sync.py",
    "backend/tests/test_member_center_prd_v1_aligned.py",
    "backend/tests/test_membership_v1.py",
    "backend/tests/test_member_center_v2.py",
    "backend/tests/test_guardian_system_v12.py",
    # admin-web
    "admin-web/src/app/(admin)/layout.tsx",
    "admin-web/src/app/(admin)/membership/plans/page.tsx",
    "admin-web/src/app/(admin)/membership/free-quota/page.tsx",
    "admin-web/src/app/(admin)/users/page.tsx",
    "admin-web/src/app/(admin)/product-system/orders/page.tsx",
    # h5-web
    "h5-web/src/app/member-center/page.tsx",
]


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()

    try:
        print("\n[1] 上传源码文件")
        missing = []
        for rel in FILES:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            if not os.path.exists(local):
                missing.append(local)
                print(f"    ⚠️ 本地缺失：{local}，跳过")
                continue
            remote = f"{REMOTE_PROJECT_DIR}/{rel}"
            remote_dir = os.path.dirname(remote)
            ssh_run(client, f"mkdir -p '{remote_dir}'", timeout=10, silent=True)
            scp_put(sftp, local, remote)
        if missing:
            print(f"⚠️ 缺失文件数: {len(missing)}")

        print("\n[2a] Rebuild backend")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build backend 2>&1 | tail -20",
            timeout=900,
        )
        print("\n[2b] Rebuild admin-web")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build admin-web 2>&1 | tail -20",
            timeout=900,
        )
        print("\n[2c] Rebuild h5-web")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -20",
            timeout=900,
        )

        print("\n[3] 重启容器")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose up -d backend admin-web h5-web 2>&1 | tail -10",
            timeout=180,
        )

        print("\n[4] 等待 backend 启动")
        ready = False
        for i in range(60):
            time.sleep(2)
            rc, out = ssh_run(
                client,
                f"docker logs --tail=60 {DEPLOY_ID}-backend 2>&1 | tail -40",
                timeout=20,
                silent=True,
            )
            if "Application startup complete" in out or "Uvicorn running" in out:
                print(f"    backend ready @ {(i + 1) * 2}s")
                ready = True
                break
            if "Traceback" in out and ("Error" in out or "Exception" in out):
                print("    ⚠️ backend 启动报错，查看完整日志：")
                ssh_run(
                    client,
                    f"docker logs --tail=200 {DEPLOY_ID}-backend 2>&1 | tail -180",
                    timeout=20,
                )
                break
        if not ready:
            print("    ⚠️ backend 未就绪 / 启动超时")

        print("\n[5] HTTP smoke 测试")
        smoke_paths = [
            "/api/openapi.json",
            "/api/admin/membership/plans",
            "/api/admin/membership/free-quota",
            "/api/member/plans",
            "/admin/membership/plans",
            "/admin/membership/free-quota",
            "/member-center",
        ]
        for path in smoke_paths:
            ssh_run(
                client,
                f"curl -sk -o /tmp/resp.txt -w '{path} → %{{http_code}}\\n' '{BASE_URL}{path}'; "
                f"head -c 200 /tmp/resp.txt | tr -d '\\r'; echo",
                timeout=20,
            )

        print("\n[6] 容器内 pytest 新测试")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_member_center_prd_v1_aligned.py -v --tb=short 2>&1 | tail -120'",
            timeout=600,
        )

        print("\n[7] 验证 schema_sync 后的 DB 字段")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health "
            f"-e 'DESCRIBE membership_plans; DESCRIBE free_member_quota;' 2>&1 | tail -50",
            timeout=30,
        )

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
