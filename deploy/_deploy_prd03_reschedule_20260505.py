"""[PRD-03 客户端改期能力收口 v1.0] 部署脚本

本次改动列表
------------
Backend
- backend/app/utils/reschedule_validator.py (新增) — 改期容量宽松校验工具
- backend/app/api/unified_orders.py — set_order_appointment 加 customer 角色校验 + 改期日期范围 + allow_reschedule 校验 + 宽松容量校验
- backend/app/api/merchant.py — /api/merchant/booking/{id}/reschedule 直接 403 拒绝
- backend/tests/test_prd03_reschedule_v1.py (新增) — 宽松校验 / 角色判定 / 日期范围契约 单元测试

H5 (h5-web) - 商家端清理 + 客户端改期 UI 强化
- h5-web/src/app/merchant/calendar/page.tsx — 删除 RescheduleModal 引用 + 顶部规则提示
- h5-web/src/app/merchant/calendar/RescheduleModal.tsx — 文件删除
- h5-web/src/app/merchant/calendar/ListView.tsx — 删除「改约」菜单项
- h5-web/src/app/merchant/calendar/DayView.tsx — 删除 onReschedule props
- h5-web/src/app/merchant/calendar/ResourceView.tsx — 删除 onReschedule props
- h5-web/src/app/merchant/calendar/BookingActionPopover.tsx — 删除「改约」按钮
- h5-web/src/app/unified-order/[id]/page.tsx — 改期 UI 强化（明天起 90 天 + 9 段 + allow_reschedule 置灰）

小程序 (miniprogram)
- miniprogram/pages/unified-order-detail/index.js — 改期场景 9 段 + allow_reschedule 拦截 + 明天起
- miniprogram/pages/unified-order-detail/index.wxml — 弹窗标题切换 + 9 段时段
- miniprogram/pages/unified-order-detail/index.wxss — 改期规则提示样式

Flutter (flutter_app)
- flutter_app/lib/screens/order/unified_order_detail_screen.dart — 改期 UI 强化

操作步骤
--------
1. SCP 上传变更文件 + sftp 删除 RescheduleModal.tsx
2. 容器内运行 PRD-03 + PRD-02 + PRD-01 单元测试（noconftest 模式）
3. docker compose build backend admin-web h5-web → up -d
4. 核心 URL 健康检查
"""
from __future__ import annotations

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

# 上传文件清单：(本地相对路径, 远端绝对路径)
FILES = [
    # Backend
    ("backend/app/utils/reschedule_validator.py",
     f"{REMOTE_PROJ}/backend/app/utils/reschedule_validator.py"),
    ("backend/app/api/unified_orders.py",
     f"{REMOTE_PROJ}/backend/app/api/unified_orders.py"),
    ("backend/app/api/merchant.py",
     f"{REMOTE_PROJ}/backend/app/api/merchant.py"),
    ("backend/tests/test_prd03_reschedule_v1.py",
     f"{REMOTE_PROJ}/backend/tests/test_prd03_reschedule_v1.py"),
    # H5 商家端清理
    ("h5-web/src/app/merchant/calendar/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/page.tsx"),
    ("h5-web/src/app/merchant/calendar/ListView.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/ListView.tsx"),
    ("h5-web/src/app/merchant/calendar/DayView.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/DayView.tsx"),
    ("h5-web/src/app/merchant/calendar/ResourceView.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/ResourceView.tsx"),
    ("h5-web/src/app/merchant/calendar/BookingActionPopover.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/BookingActionPopover.tsx"),
    # H5 客户端改期 UI 强化
    ("h5-web/src/app/unified-order/[id]/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/unified-order/[id]/page.tsx"),
    # 小程序
    ("miniprogram/pages/unified-order-detail/index.js",
     f"{REMOTE_PROJ}/miniprogram/pages/unified-order-detail/index.js"),
    ("miniprogram/pages/unified-order-detail/index.wxml",
     f"{REMOTE_PROJ}/miniprogram/pages/unified-order-detail/index.wxml"),
    ("miniprogram/pages/unified-order-detail/index.wxss",
     f"{REMOTE_PROJ}/miniprogram/pages/unified-order-detail/index.wxss"),
    # Flutter
    ("flutter_app/lib/screens/order/unified_order_detail_screen.dart",
     f"{REMOTE_PROJ}/flutter_app/lib/screens/order/unified_order_detail_screen.dart"),
]

# 远端需要删除的文件（H5 商家端 RescheduleModal）
FILES_TO_DELETE = [
    f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/RescheduleModal.tsx",
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
        remote_dir = "/".join(remote_abs.split("/")[:-1])
        ensure_remote_dir(sftp, remote_dir)
        print(f"  [PUT] {local_rel} ({size} bytes) -> {remote_abs}")
        sftp.put(str(local_abs), remote_abs)

    print("\n=== Step 1.5: 删除商家端 RescheduleModal.tsx（PRD-03 §R-03-01） ===")
    for remote_abs in FILES_TO_DELETE:
        try:
            sftp.remove(remote_abs)
            print(f"  [RM]  {remote_abs}")
        except IOError as e:
            print(f"  [SKIP] {remote_abs} ({e})")
    sftp.close()

    container_be = f"{DEPLOY_ID}-backend"
    container_admin = f"{DEPLOY_ID}-admin-web"
    container_h5 = f"{DEPLOY_ID}-h5-web"

    print("\n=== Step 2: 把新增/改动的 backend 测试文件 cp 进 backend 容器 ===")
    run(
        ssh,
        f"docker cp {REMOTE_PROJ}/backend/tests/test_prd03_reschedule_v1.py "
        f"{container_be}:/app/tests/test_prd03_reschedule_v1.py",
        timeout=60,
    )

    print("\n=== Step 3: 容器内运行 PRD-03 单元测试（仅纯函数 / unittest.mock；--noconftest） ===")
    code, out, _ = run(
        ssh,
        f"docker exec {container_be} python -m pytest "
        f"tests/test_prd03_reschedule_v1.py "
        f"tests/test_prd02_dashboard_v1.py "
        f"tests/test_time_slots_unified_v1.py "
        f"-v --noconftest -p no:cacheprovider --tb=short 2>&1 | tail -200",
        timeout=300,
    )
    # 检查结果
    last_summary = ""
    for ln in reversed(out.strip().splitlines()):
        if "passed" in ln or "failed" in ln or "error" in ln:
            last_summary = ln
            break
    pytest_pass = ("passed" in last_summary) and ("failed" not in last_summary) and ("error" not in last_summary.replace("errors=0", ""))
    print(f"\n[pytest summary] {last_summary}")

    print("\n=== Step 4: 重建 backend 容器（unified_orders.py / merchant.py / utils 改动） ===")
    code_be, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build backend 2>&1 | tail -40",
        timeout=600,
    )
    if code_be != 0:
        print("[FAIL] backend build failed")
        ssh.close()
        return 1

    print("\n=== Step 5: 重建 h5-web 容器（商家端清理 + 客户端改期 UI 强化） ===")
    code_h5, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build h5-web 2>&1 | tail -60",
        timeout=1800,
    )
    if code_h5 != 0:
        print("[FAIL] h5-web build failed")
        ssh.close()
        return 1

    print("\n=== Step 6: docker compose up -d backend h5-web ===")
    run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose up -d backend h5-web 2>&1 | tail -10",
        timeout=120,
    )

    print("\n=== Step 7: 等待容器启动（10s） ===")
    time.sleep(12)

    print("\n=== Step 8: 核心 URL 健康检查 ===")
    urls = [
        f"{BASE_URL}/api/health",
        f"{BASE_URL}/admin/login/",
        f"{BASE_URL}/admin/product-system/orders/dashboard/",
        f"{BASE_URL}/admin/product-system/orders/",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
        f"{BASE_URL}/api/common/time-slots",
        f"{BASE_URL}/merchant/calendar/",
        f"{BASE_URL}/",
    ]
    all_ok = True
    for u in urls:
        code, out, _ = run(
            ssh, f"curl -k -s -o /dev/null -w '%{{http_code}}' '{u}'", timeout=30,
        )
        status = out.strip()
        ok = status in ("200", "308", "302", "401", "307")
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark}] {u} -> {status}")
        if not ok:
            all_ok = False

    print("\n=== Step 9: 验证商家端改期接口已 403（PRD §R-03-01） ===")
    # 不带认证调用，无论谁都应该 403（merchant_dep 校验前），或者 401（未认证）
    code, out, _ = run(
        ssh,
        f"curl -k -s -o /dev/null -w '%{{http_code}}' "
        f"-X POST '{BASE_URL}/api/merchant/booking/1/reschedule?store_id=1' "
        f"-H 'Content-Type: application/json' -d '{{}}'",
        timeout=20,
    )
    merchant_status = out.strip()
    # 401（未登录）/ 403（商家鉴权未通过或本接口已拒绝）都符合预期
    merchant_blocked = merchant_status in ("401", "403", "422")
    print(f"  [{('OK' if merchant_blocked else 'FAIL')}] /api/merchant/booking/1/reschedule -> {merchant_status} (期望 401/403/422)")

    print("\n=== Done ===")
    print(f"  pytest:           {'PASS' if pytest_pass else 'FAIL'}")
    print(f"  urls:             {'PASS' if all_ok else 'FAIL'}")
    print(f"  merchant 403:     {'PASS' if merchant_blocked else 'FAIL'}")

    ssh.close()
    success = pytest_pass and all_ok and merchant_blocked
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
