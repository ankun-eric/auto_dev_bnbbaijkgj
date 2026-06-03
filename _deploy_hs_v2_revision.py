"""[BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28] 部署 + 测试脚本

工作内容：
1. 上传后端 home_safety_v1.py 与新测试 test_home_safety_v2_revision.py
2. 上传 admin-web/src/app/(admin)/home-safety/page.tsx
3. 重启 backend 容器（自动建表新增字段）
4. 重建 admin-web 容器
5. 在 backend 容器内运行 pytest 验证
6. 通过外部 HTTP 烟雾测试新接口
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "backend/app/api/home_safety_v1.py",
    "backend/tests/test_home_safety_v2_revision.py",
    "admin-web/src/app/(admin)/home-safety/page.tsx",
]


def run(c: paramiko.SSHClient, cmd: str, t: int = 600) -> tuple[str, str, int]:
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print("[err]", err)
    return out, err, rc


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[CONNECT] {HOST}")
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = c.open_sftp()

    # 上传文件
    for rel in FILES:
        local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
        remote = f"{REMOTE_BASE}/{rel}"
        # 确保远程目录存在
        rdir = remote.rsplit("/", 1)[0]
        run(c, f"mkdir -p '{rdir}'")
        if not os.path.exists(local):
            print(f"[SKIP] 本地文件不存在: {local}")
            continue
        print(f"[UPLOAD] {rel} ({os.path.getsize(local)} bytes)")
        sftp.put(local, remote)
    sftp.close()

    # 重启 backend
    run(c, f"cd {REMOTE_BASE} && docker compose restart backend 2>&1 | tail -10")
    time.sleep(8)

    # backend 健康
    out, _, _ = run(c, f"cd {REMOTE_BASE} && docker compose ps backend")
    print(out)

    # 在 backend 容器内运行 pytest（仅运行新测试 + 原 home_safety v1 测试，确保兼容）
    print("\n========== 运行后端测试：test_home_safety_v2_revision + test_home_safety_v1 ==========")
    test_cmd = (
        f"cd {REMOTE_BASE} && docker compose exec -T backend "
        f"python -m pytest tests/test_home_safety_v1.py tests/test_home_safety_v2_revision.py "
        f"-v --tb=short -x 2>&1 | tail -120"
    )
    out, _, rc = run(c, test_cmd, t=600)
    test_passed = ("passed" in out) and ("failed" not in out or "0 failed" in out)

    # 重建 admin-web（避免引起前端编译错误时卡住整流程，先打到独立 timeout）
    print("\n========== 重建 admin-web ==========")
    run(c, f"cd {REMOTE_BASE} && docker compose up -d --build admin-web 2>&1 | tail -30", t=900)
    time.sleep(10)
    run(c, f"cd {REMOTE_BASE} && docker compose ps admin-web")

    # 烟雾：新接口 GET callback_log（应 401 因为未鉴权）
    print("\n========== 外部 HTTP 烟雾测试 ==========")
    base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    smoke_cmd = (
        f"curl -sk -o /dev/null -w '%{{http_code}}' "
        f"'{base_url}/api/admin/home_safety/callback_log?page=1&size=10'"
    )
    run(c, smoke_cmd)

    smoke_cmd2 = (
        f"curl -sk -o /dev/null -w '%{{http_code}}' "
        f"-X POST -H 'Content-Type: application/json' "
        f"-d '{{\"dataType\":\"__precheck__\",\"msgId\":\"smoke-precheck\",\"param\":{{}}}}' "
        f"'{base_url}/api/home_safety/callback/alarm'"
    )
    run(c, smoke_cmd2)

    c.close()

    if not test_passed:
        print("\n[!!!] 后端测试未通过，请查看上面输出。")
        sys.exit(1)
    else:
        print("\n[OK] 后端测试通过。")


if __name__ == "__main__":
    main()
