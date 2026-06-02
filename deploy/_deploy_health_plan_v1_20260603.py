"""[PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-03]
将本次健康计划重做版的所有变更同步到远程服务器并重启容器。

改动范围：
- backend：app/api/health_plan_v2.py、app/api/admin_health_plan.py、app/schemas/health_plan_v2.py
  以及其他 family.py / family_self_backfill_migration.py 等
- h5-web：app/health-plan/page.tsx、app/health-plan/checkin/page.tsx
  app/health-plan/edit/page.tsx、app/health-plan/result/page.tsx
- 测试：backend/tests/test_health_plan_checkin_v1_20260602.py
"""
import io
import os
import sys
import tarfile
import time

import paramiko

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sshlib import HOST, PORT, USER, PASSWORD, DEPLOY_ID, get_client, run

REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def upload_file(sftp, local_path, remote_path):
    parent = os.path.dirname(remote_path).replace("\\", "/")
    try:
        sftp.stat(parent)
    except IOError:
        # 递归 mkdir
        parts = parent.split("/")
        cur = ""
        for p in parts:
            if not p:
                cur = "/"
                continue
            cur = cur.rstrip("/") + "/" + p if cur != "/" else "/" + p
            try:
                sftp.stat(cur)
            except IOError:
                try:
                    sftp.mkdir(cur)
                except Exception:
                    pass
    print(f"[upload] {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)


def main():
    files = [
        # backend
        ("backend/app/api/health_plan_v2.py", "backend/app/api/health_plan_v2.py"),
        ("backend/app/api/admin_health_plan.py", "backend/app/api/admin_health_plan.py"),
        ("backend/app/api/family.py", "backend/app/api/family.py"),
        ("backend/app/schemas/health_plan_v2.py", "backend/app/schemas/health_plan_v2.py"),
        ("backend/app/services/family_self_backfill_migration.py",
         "backend/app/services/family_self_backfill_migration.py"),
        ("backend/tests/test_health_plan_checkin_v1_20260602.py",
         "backend/tests/test_health_plan_checkin_v1_20260602.py"),
        # h5
        ("h5-web/src/app/health-plan/page.tsx", "h5-web/src/app/health-plan/page.tsx"),
        ("h5-web/src/app/health-plan/checkin/page.tsx", "h5-web/src/app/health-plan/checkin/page.tsx"),
        ("h5-web/src/app/health-plan/edit/page.tsx", "h5-web/src/app/health-plan/edit/page.tsx"),
        ("h5-web/src/app/health-plan/result/page.tsx", "h5-web/src/app/health-plan/result/page.tsx"),
    ]

    c = get_client()
    sftp = c.open_sftp()
    try:
        for local_rel, remote_rel in files:
            local_full = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            remote_full = f"{REMOTE_DIR}/{remote_rel}"
            if not os.path.exists(local_full):
                print(f"[SKIP missing] {local_full}")
                continue
            upload_file(sftp, local_full, remote_full)
    finally:
        sftp.close()
        c.close()

    print("\n[1] 上传完成，重启 backend 容器...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose restart backend 2>&1 | tail -20",
        timeout=120,
    )
    print(out)
    if err:
        print("STDERR:", err)
    if code != 0:
        print("backend 重启失败 (will retry once)")
        time.sleep(2)
        code, out, err = run(
            f"cd {REMOTE_DIR} && docker compose restart backend 2>&1",
            timeout=120,
        )
        print(out)

    print("\n[2] 等待 backend 启动 (8s)...")
    time.sleep(8)

    print("\n[3] 健康检查...")
    code, out, err = run(
        f"curl -sk -o /dev/null -w '%{{http_code}}' "
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health 2>&1",
        timeout=30,
    )
    print(f"backend health -> {out.strip()}")

    print("\n[4] 重新构建并启动 h5-web...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose build h5-web 2>&1 | tail -30",
        timeout=600,
    )
    print(out)

    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose up -d h5-web 2>&1 | tail -10",
        timeout=120,
    )
    print(out)

    print("\n[5] 等待 h5 启动 (10s)...")
    time.sleep(10)

    code, out, err = run(
        f"curl -sk -o /dev/null -w '%{{http_code}}' "
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-plan 2>&1",
        timeout=30,
    )
    print(f"/health-plan -> {out.strip()}")

    print("\n部署完成。")


if __name__ == "__main__":
    main()
