"""[PRD-FAMILY-V3-EMERGENCY-FIX + PRD-FAMILY-V3-STATE-MODEL-V1 2026-06-03]

V3 终版 — 家庭成员状态模型 & 一人一档治本(第一阶段:应急修复 + V3 后端基础)
部署脚本。

改动文件:
后端:
- backend/app/services/family_status_constants.py   (新建)
- backend/app/services/family_member_status.py      (新建)
- backend/app/api/family.py                          (注入 V3 字段)
- backend/app/api/family_member_v2.py                (统一过滤口径)
- backend/app/api/health_profile.py                  (member 接口对齐过滤)
- backend/tests/test_family_v3_state_model_20260603.py (10 项测试)

H5:
- h5-web/src/app/health-profile/page.tsx (极简视图 + 重新邀请按钮)

部署步骤:
1. SFTP 上传 7 文件
2. docker compose build & up backend
3. 容器内 pytest 验证 V3 测试 10/10
4. docker compose build & up h5-web
5. 外部 HTTPS smoke 测试
"""
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sshlib import HOST, PORT, USER, PASSWORD, DEPLOY_ID, get_client, run

REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def upload_file(sftp, local_path, remote_path):
    parent = os.path.dirname(remote_path).replace("\\", "/")
    try:
        sftp.stat(parent)
    except IOError:
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
        ("backend/app/services/family_status_constants.py",
         "backend/app/services/family_status_constants.py"),
        ("backend/app/services/family_member_status.py",
         "backend/app/services/family_member_status.py"),
        ("backend/app/api/family.py", "backend/app/api/family.py"),
        ("backend/app/api/family_member_v2.py", "backend/app/api/family_member_v2.py"),
        ("backend/app/api/health_profile.py", "backend/app/api/health_profile.py"),
        ("backend/tests/test_family_v3_state_model_20260603.py",
         "backend/tests/test_family_v3_state_model_20260603.py"),
        # h5
        ("h5-web/src/app/health-profile/page.tsx",
         "h5-web/src/app/health-profile/page.tsx"),
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

    print("\n[1] 上传完成,重新构建后端容器...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose build backend 2>&1 | tail -25",
        timeout=600,
    )
    print(out)

    print("\n[2] 重启 backend 容器...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose up -d backend 2>&1 | tail -10",
        timeout=120,
    )
    print(out)

    print("\n[3] 等待 backend 启动 (10s)...")
    time.sleep(10)

    print("\n[4] /api/health 健康检查...")
    code, out, err = run(
        f"curl -sk -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/health 2>&1",
        timeout=30,
    )
    print(f"  /api/health -> {out.strip()}")

    print("\n[5] 容器内运行 V3 测试...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose exec -T backend python -m pytest "
        f"tests/test_family_v3_state_model_20260603.py -v --tb=short 2>&1 | tail -50",
        timeout=180,
    )
    print(out)

    print("\n[6] 重新构建并启动 h5-web...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose build h5-web 2>&1 | tail -25",
        timeout=900,
    )
    print(out[-2000:] if out else '(no output)')

    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose up -d h5-web 2>&1 | tail -10",
        timeout=120,
    )
    print(out)

    print("\n[7] 等待 h5 启动 (12s)...")
    time.sleep(12)

    print("\n[8] 外部 HTTPS smoke 测试...")
    for path in ["/api/health", "/health-profile/", "/api/family/members"]:
        code, out, err = run(
            f"curl -sk -o /dev/null -w '%{{http_code}}' {BASE_URL}{path} 2>&1",
            timeout=30,
        )
        print(f"  {path} -> {out.strip()}")

    print("\n部署完成。")


if __name__ == "__main__":
    main()
