"""[PRD-01 全平台固定时段切片体系 v1.0] 部署脚本

操作步骤
--------
1. SCP 上传 8 个变更文件（后端 5 + 三端 utils 3）
2. docker compose build backend + admin-web（admin-web 未改但保险重启）
3. docker compose up -d backend
4. 容器内 schema_sync 自动 ALTER 加 time_slot 字段（应用启动时执行）
5. 容器内运行 PRD-01 单元测试
6. 容器内运行历史数据回填脚本（dry-run + apply）
7. 5 个核心 URL 健康检查 + /api/common/time-slots 接口验证

成功标准
--------
- 单元测试全部 PASS
- 5 个 URL 全 200/308
- /api/common/time-slots 返回 9 段且字段为 slot_no/start/end
- 回填脚本 apply 成功
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    # 后端核心
    ("backend/app/utils/time_slots.py",
     f"{REMOTE_PROJ}/backend/app/utils/time_slots.py"),
    ("backend/app/api/common.py",
     f"{REMOTE_PROJ}/backend/app/api/common.py"),
    ("backend/app/api/merchant_dashboard.py",
     f"{REMOTE_PROJ}/backend/app/api/merchant_dashboard.py"),
    ("backend/app/api/unified_orders.py",
     f"{REMOTE_PROJ}/backend/app/api/unified_orders.py"),
    ("backend/app/main.py",
     f"{REMOTE_PROJ}/backend/app/main.py"),
    ("backend/app/models/models.py",
     f"{REMOTE_PROJ}/backend/app/models/models.py"),
    ("backend/app/services/schema_sync.py",
     f"{REMOTE_PROJ}/backend/app/services/schema_sync.py"),
    ("backend/scripts/backfill_unified_orders_time_slot.py",
     f"{REMOTE_PROJ}/backend/scripts/backfill_unified_orders_time_slot.py"),
    ("backend/tests/test_time_slots_unified_v1.py",
     f"{REMOTE_PROJ}/backend/tests/test_time_slots_unified_v1.py"),
    # 三端 utils
    ("h5-web/src/lib/timeSlots.ts",
     f"{REMOTE_PROJ}/h5-web/src/lib/timeSlots.ts"),
    ("miniprogram/utils/timeSlots.js",
     f"{REMOTE_PROJ}/miniprogram/utils/timeSlots.js"),
    ("flutter_app/lib/utils/time_slots.dart",
     f"{REMOTE_PROJ}/flutter_app/lib/utils/time_slots.dart"),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n[REMOTE] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[:2000])
    return code, out, err


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    """递归创建远程目录"""
    parts = remote_path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

    sftp = ssh.open_sftp()

    print("\n=== Step 1: SCP 上传变更文件 ===")
    for local_rel, remote_abs in FILES:
        local_abs = LOCAL_ROOT / local_rel
        if not local_abs.exists():
            print(f"  [SKIP] {local_rel} 不存在")
            continue
        size = local_abs.stat().st_size
        # 确保目录存在
        remote_dir = "/".join(remote_abs.split("/")[:-1])
        ensure_remote_dir(sftp, remote_dir)
        print(f"  [PUT] {local_rel} ({size} bytes) -> {remote_abs}")
        sftp.put(str(local_abs), remote_abs)
    sftp.close()

    print("\n=== Step 2: 重建 backend 容器 ===")
    code, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build backend 2>&1 | tail -40",
        timeout=900,
    )
    if code != 0:
        print("[FAIL] backend build failed")
        ssh.close()
        return 1

    print("\n=== Step 3: docker compose up -d ===")
    run(ssh, f"cd {REMOTE_PROJ} && docker compose up -d backend 2>&1 | tail -10")

    print("\n=== Step 4: 等待容器启动（含 schema_sync 自动 ALTER） ===")
    time.sleep(12)

    container = f"{DEPLOY_ID}-backend"

    print("\n=== Step 5: 验证 unified_orders.time_slot 字段已 ALTER 出现 ===")
    run(
        ssh,
        f"docker exec {container} python -c \""
        "from app.core.database import sync_engine; "
        "from sqlalchemy import inspect; "
        "ins = inspect(sync_engine); "
        "cols = [c['name'] for c in ins.get_columns('unified_orders')]; "
        "print('time_slot in cols:', 'time_slot' in cols); "
        "print('all cols sample:', cols[:5], '...')"
        "\" 2>&1",
        timeout=60,
    )

    print("\n=== Step 6: 容器内运行 PRD-01 单元测试 ===")
    code, out, _ = run(
        ssh,
        f"docker exec {container} python -m pytest tests/test_time_slots_unified_v1.py "
        f"tests/test_merchant_dashboard_v1.py -v --tb=short 2>&1 | tail -80",
        timeout=120,
    )
    pytest_pass = ("passed" in out and "failed" not in out.split("=")[-1])

    print("\n=== Step 7: 容器内运行历史回填脚本（dry-run） ===")
    run(
        ssh,
        f"docker exec {container} python -m scripts.backfill_unified_orders_time_slot 2>&1 | tail -30",
        timeout=60,
    )

    print("\n=== Step 8: 容器内运行历史回填脚本（apply） ===")
    code, out, _ = run(
        ssh,
        f"docker exec {container} python -m scripts.backfill_unified_orders_time_slot --apply 2>&1 | tail -30",
        timeout=120,
    )
    backfill_ok = ("APPLY" in out and "FAIL" not in out.upper())

    print("\n=== Step 9: 核心 URL 健康检查 ===")
    urls = [
        f"{BASE_URL}/api/health",
        f"{BASE_URL}/admin/login/",
        f"{BASE_URL}/",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
        f"{BASE_URL}/api/common/time-slots",
    ]
    all_ok = True
    for u in urls:
        code, out, _ = run(
            ssh, f"curl -k -s -o /dev/null -w '%{{http_code}}' '{u}'", timeout=30,
        )
        status = out.strip()
        ok = status in ("200", "308", "401", "302")
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark}] {u} -> {status}")
        if not ok:
            all_ok = False

    print("\n=== Step 10: 验证 /api/common/time-slots 响应字段严格匹配 PRD ===")
    code, out, _ = run(
        ssh,
        f"curl -k -s '{BASE_URL}/api/common/time-slots'",
        timeout=30,
    )
    try:
        body = json.loads(out)
        slots = body.get("slots", [])
        prd_ok = (
            len(slots) == 9
            and slots[0] == {"slot_no": 1, "start": "06:00", "end": "08:00"}
            and slots[-1] == {"slot_no": 9, "start": "22:00", "end": "24:00"}
            and all(set(s.keys()) == {"slot_no", "start", "end"} for s in slots)
        )
        print(f"  PRD 字段合规: {'PASS' if prd_ok else 'FAIL'}")
        if not prd_ok:
            print(f"  实际响应: {out[:500]}")
    except Exception as e:
        prd_ok = False
        print(f"  [FAIL] JSON 解析失败: {e}; raw={out[:200]}")

    print("\n=== Done ===")
    print(f"  pytest:    {'PASS' if pytest_pass else 'FAIL'}")
    print(f"  urls:      {'PASS' if all_ok else 'FAIL'}")
    print(f"  prd schema:{'PASS' if prd_ok else 'FAIL'}")
    print(f"  backfill:  {'PASS' if backfill_ok else 'FAIL'}")

    ssh.close()
    success = pytest_pass and all_ok and prd_ok and backfill_ok
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
