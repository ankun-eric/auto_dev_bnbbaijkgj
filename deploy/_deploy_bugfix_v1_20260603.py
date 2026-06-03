"""[BUGFIX V1 2026-06-03] 5 项 Bug 修复部署脚本

改动文件:
- backend/app/api/family.py              (旧 1: 显式 sub_status)
- backend/app/api/family_management.py   (旧 1: 接受邀请新建家人补 sub_status)
- backend/app/services/schema_sync.py    (旧 2: 2.4 任务列名修复)
- backend/tests/test_bugfix_v1_20260603.py (回归测试)
- h5-web/src/components/family/FamilyMemberTabs.tsx (新 1: 已解绑文字 -> 右上角绿勾)
- h5-web/src/app/health-profile/page.tsx (新 2: Hero 邀请按钮橙色渐变)
- miniprogram/pages/health-profile/index.wxss (新 2: 小程序对齐)

流程:
1. SFTP 上传文件
2. docker compose build & up backend
3. 容器内 pytest 验证回归
4. docker compose build & up h5-web
5. 外部 HTTPS smoke 测试
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sshlib import DEPLOY_ID, get_client, run

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
        ("backend/app/api/family.py", "backend/app/api/family.py"),
        ("backend/app/api/family_management.py", "backend/app/api/family_management.py"),
        ("backend/app/services/schema_sync.py", "backend/app/services/schema_sync.py"),
        ("backend/tests/test_bugfix_v1_20260603.py",
         "backend/tests/test_bugfix_v1_20260603.py"),
        # h5
        ("h5-web/src/components/family/FamilyMemberTabs.tsx",
         "h5-web/src/components/family/FamilyMemberTabs.tsx"),
        ("h5-web/src/app/health-profile/page.tsx",
         "h5-web/src/app/health-profile/page.tsx"),
        # miniprogram (即使不在容器内,文件也同步过去,便于后续打包)
        ("miniprogram/pages/health-profile/index.wxss",
         "miniprogram/pages/health-profile/index.wxss"),
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
        timeout=900,
    )
    print(out)

    print("\n[2] 重启 backend 容器...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose up -d backend 2>&1 | tail -10",
        timeout=180,
    )
    print(out)

    print("\n[3] 等待 backend 启动 (12s)...")
    time.sleep(12)

    print("\n[4] /api/health 健康检查...")
    code, out, err = run(
        f"curl -sk -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/health 2>&1",
        timeout=30,
    )
    print(f"  /api/health -> {out.strip()}")

    print("\n[5] 容器内运行 BUGFIX V1 回归测试...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose exec -T backend python -m pytest "
        f"tests/test_bugfix_v1_20260603.py -v --tb=short 2>&1 | tail -60",
        timeout=180,
    )
    print(out)

    print("\n[6] 容器内运行已有 V3 状态回归测试(确认未被破坏)...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose exec -T backend python -m pytest "
        f"tests/test_family_v3_state_model_20260603.py -v --tb=short 2>&1 | tail -50",
        timeout=240,
    )
    print(out)

    print("\n[7] 重新构建并启动 h5-web...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose build h5-web 2>&1 | tail -30",
        timeout=1200,
    )
    print((out or '')[-3000:])

    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose up -d h5-web 2>&1 | tail -10",
        timeout=180,
    )
    print(out)

    print("\n[8] 等待 h5 启动 (15s)...")
    time.sleep(15)

    print("\n[9] 外部 HTTPS smoke 测试...")
    for path in [
        "/api/health",
        "/health-profile/",
        "/home-safety/",
        "/api/family/members",
    ]:
        code, out, err = run(
            f"curl -sk -o /dev/null -w '%{{http_code}}' {BASE_URL}{path} 2>&1",
            timeout=30,
        )
        print(f"  {path} -> {out.strip()}")

    print("\n部署完成。")


if __name__ == "__main__":
    main()
