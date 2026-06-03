"""[BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03]
守护我的人 · Bug 修复部署脚本

改动文件:
- backend/app/api/reverse_guardian.py        (删除自动 cancel 旧 pending 的逻辑)
- backend/tests/test_guardian_multi_pending_20260603.py (后端回归测试)
- h5-web/src/app/health-profile/my-guardians/page.tsx       (列表卡片样式 + 上限 + 抽屉)
- h5-web/src/app/health-profile/my-guardians/invite/page.tsx (两步切换 + 确认按钮 + 直回列表)

流程:
1. SFTP 上传文件
2. backend docker compose build & up
3. 容器内 pytest 验证多 pending + 上限
4. h5-web docker compose build & up
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
        ("backend/app/api/reverse_guardian.py",
         "backend/app/api/reverse_guardian.py"),
        ("backend/tests/test_guardian_multi_pending_20260603.py",
         "backend/tests/test_guardian_multi_pending_20260603.py"),
        ("h5-web/src/app/health-profile/my-guardians/page.tsx",
         "h5-web/src/app/health-profile/my-guardians/page.tsx"),
        ("h5-web/src/app/health-profile/my-guardians/invite/page.tsx",
         "h5-web/src/app/health-profile/my-guardians/invite/page.tsx"),
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

    print("\n[1] 重启 backend (代码用 volume 挂载，无需 rebuild)...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose restart backend 2>&1 | tail -10",
        timeout=180,
    )
    print(out)

    print("\n[2] 等待 backend 启动 (10s)...")
    time.sleep(10)

    print("\n[3] /api/health 健康检查...")
    code, out, err = run(
        f"curl -sk -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/health 2>&1",
        timeout=30,
    )
    print(f"  /api/health -> {out.strip()}")

    print("\n[4] 容器内运行新增的 BUGFIX 回归测试...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose exec -T backend python -m pytest "
        f"tests/test_guardian_multi_pending_20260603.py -v --tb=short 2>&1 | tail -80",
        timeout=240,
    )
    print(out)

    print("\n[5] 容器内运行 reverse_guardian 原有回归(确认未被破坏)...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose exec -T backend python -m pytest "
        f"tests/test_reverse_guardian.py -v --tb=short 2>&1 | tail -50",
        timeout=300,
    )
    print(out)

    print("\n[6] 重新构建并启动 h5-web...")
    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose build h5-web 2>&1 | tail -30",
        timeout=1500,
    )
    print((out or '')[-3000:])

    code, out, err = run(
        f"cd {REMOTE_DIR} && docker compose up -d h5-web 2>&1 | tail -10",
        timeout=180,
    )
    print(out)

    print("\n[7] 等待 h5 启动 (15s)...")
    time.sleep(15)

    print("\n[8] 外部 HTTPS smoke 测试...")
    for path in [
        "/api/health",
        "/health-profile/my-guardians",
        "/health-profile/my-guardians/invite",
        "/api/reverse-guardian/guardian-count",
    ]:
        code, out, err = run(
            f"curl -sk -o /dev/null -w '%{{http_code}}' {BASE_URL}{path} 2>&1",
            timeout=30,
        )
        print(f"  {path} -> {out.strip()}")

    print("\n部署完成。")


if __name__ == "__main__":
    main()
