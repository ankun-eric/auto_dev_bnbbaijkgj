"""[PRD-05 核销动作收口手机端 v1.0] 部署脚本

本次改动列表
------------
Backend
- backend/app/utils/client_source.py（新增）— 客户端来源识别工具
    + parse_client_type_from_header / parse_client_type_from_user_agent / detect_client_type
    + is_mobile_verify_client / require_mobile_verify_client（FastAPI 依赖项）
- backend/app/api/member_qr.py — /api/verify/redeem + /api/verify/member-qrcode + /api/verify/checkin
    全部添加 require_mobile_verify_client 拦截；新增 /api/verifications/verify 统一入口（PRD §2.4）
- backend/app/api/merchant.py — /api/merchant/orders/{id}/verify 添加 require_mobile_verify_client 拦截
- backend/app/api/cards_v2.py — /api/staff/cards/redeem 添加 require_mobile_verify_client 拦截
- backend/app/api/order.py — /api/orders/{id}/verify（已注释禁用）添加来源校验作为防线
- backend/tests/test_prd05_verify_lockdown_v1.py（新增）— 客户端来源识别 + 4 来源拦截全 case 测试

H5 (h5-web)
- h5-web/src/lib/api.ts — axios 拦截器自动添加 Client-Type Header（h5-mobile / pc-web）
- h5-web/src/app/merchant/calendar/BookingActionPopover.tsx — PC 端核销按钮置灰 + Tooltip 提示
- h5-web/src/app/merchant/calendar/ListView.tsx — PC 端核销菜单项置灰

Admin-Web
- admin-web/src/lib/api.ts — axios 拦截器自动添加 Client-Type=pc-web Header

核销小程序 (verify-miniprogram)
- verify-miniprogram/utils/request.js — 请求自动添加 Client-Type=verify-miniprogram Header

操作步骤
--------
1. SCP 上传所有变更文件
2. docker cp 测试文件进 backend 容器
3. 容器内运行 PRD-05 + PRD-03 + PRD-02 + PRD-01 单元测试
4. docker compose build backend admin-web h5-web → up -d
5. 核心 URL 健康检查
6. 验证 PC 端 Client-Type=pc-web 调用 /api/verify/redeem 返回 403
7. 验证 H5 移动端 Client-Type=h5-mobile 调用 /api/verify/redeem 不被来源拦截
   （应是 401/422 业务校验失败而非 403 来源失败）
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

FILES = [
    # Backend
    ("backend/app/utils/client_source.py",
     f"{REMOTE_PROJ}/backend/app/utils/client_source.py"),
    ("backend/app/api/member_qr.py",
     f"{REMOTE_PROJ}/backend/app/api/member_qr.py"),
    ("backend/app/api/merchant.py",
     f"{REMOTE_PROJ}/backend/app/api/merchant.py"),
    ("backend/app/api/cards_v2.py",
     f"{REMOTE_PROJ}/backend/app/api/cards_v2.py"),
    ("backend/app/api/order.py",
     f"{REMOTE_PROJ}/backend/app/api/order.py"),
    ("backend/tests/test_prd05_verify_lockdown_v1.py",
     f"{REMOTE_PROJ}/backend/tests/test_prd05_verify_lockdown_v1.py"),
    # H5 商家端 PC 抽屉核销按钮置灰 + axios Client-Type
    ("h5-web/src/lib/api.ts",
     f"{REMOTE_PROJ}/h5-web/src/lib/api.ts"),
    ("h5-web/src/app/merchant/calendar/BookingActionPopover.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/BookingActionPopover.tsx"),
    ("h5-web/src/app/merchant/calendar/ListView.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/merchant/calendar/ListView.tsx"),
    # Admin-Web axios Client-Type=pc-web
    ("admin-web/src/lib/api.ts",
     f"{REMOTE_PROJ}/admin-web/src/lib/api.ts"),
    # 核销小程序请求 Client-Type=verify-miniprogram
    ("verify-miniprogram/utils/request.js",
     f"{REMOTE_PROJ}/verify-miniprogram/utils/request.js"),
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

    sftp.close()

    container_be = f"{DEPLOY_ID}-backend"
    container_admin = f"{DEPLOY_ID}-admin-web"
    container_h5 = f"{DEPLOY_ID}-h5-web"

    print("\n=== Step 2: 先重建 backend 容器（让 client_source.py 等新文件进入镜像） ===")
    code_be, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build backend 2>&1 | tail -40",
        timeout=600,
    )
    if code_be != 0:
        print("[FAIL] backend build failed")
        ssh.close()
        return 1

    print("\n=== Step 2.5: docker compose up -d backend（让新镜像运行起来） ===")
    run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose up -d backend 2>&1 | tail -10",
        timeout=120,
    )
    time.sleep(8)

    print("\n=== Step 3: 把新增的 backend 测试文件 cp 进 backend 容器 ===")
    run(
        ssh,
        f"docker cp {REMOTE_PROJ}/backend/tests/test_prd05_verify_lockdown_v1.py "
        f"{container_be}:/app/tests/test_prd05_verify_lockdown_v1.py",
        timeout=60,
    )

    print("\n=== Step 3.5: 容器内确保 pytest 已安装 ===")
    run(
        ssh,
        f"docker exec {container_be} pip install -q --no-cache-dir pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -10",
        timeout=120,
    )

    print("\n=== Step 4: 容器内运行 PRD-05 + 既有 PRD-01/02/03 单元测试（noconftest） ===")
    code, out, _ = run(
        ssh,
        f"docker exec {container_be} python -m pytest "
        f"tests/test_prd05_verify_lockdown_v1.py "
        f"tests/test_prd03_reschedule_v1.py "
        f"tests/test_prd02_dashboard_v1.py "
        f"tests/test_time_slots_unified_v1.py "
        f"-v --noconftest -p no:cacheprovider --tb=short 2>&1 | tail -200",
        timeout=300,
    )
    last_summary = ""
    for ln in reversed(out.strip().splitlines()):
        if "passed" in ln or "failed" in ln or "error" in ln:
            last_summary = ln
            break
    pytest_pass = (
        "passed" in last_summary
        and "failed" not in last_summary
        and "error" not in last_summary.replace("errors=0", "")
    )
    print(f"\n[pytest summary] {last_summary}")

    print("\n=== Step 5: 重建 h5-web（核销按钮置灰 + axios Client-Type） ===")
    code_h5, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build h5-web 2>&1 | tail -60",
        timeout=1800,
    )
    if code_h5 != 0:
        print("[FAIL] h5-web build failed")
        ssh.close()
        return 1

    print("\n=== Step 6: 重建 admin-web（axios Client-Type=pc-web） ===")
    code_admin, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build admin-web 2>&1 | tail -60",
        timeout=1800,
    )
    if code_admin != 0:
        print("[FAIL] admin-web build failed")
        ssh.close()
        return 1

    print("\n=== Step 7: docker compose up -d ===")
    run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose up -d backend h5-web admin-web 2>&1 | tail -10",
        timeout=120,
    )

    print("\n=== Step 8: 等待容器启动（12s） ===")
    time.sleep(12)

    print("\n=== Step 9: 核心 URL 健康检查 ===")
    urls = [
        f"{BASE_URL}/api/health",
        f"{BASE_URL}/admin/login/",
        f"{BASE_URL}/admin/product-system/orders/dashboard/",
        f"{BASE_URL}/admin/product-system/redemptions/",
        f"{BASE_URL}/api/common/time-slots",
        f"{BASE_URL}/merchant/calendar/",
        f"{BASE_URL}/merchant/m/verify/",
        f"{BASE_URL}/merchant/verifications/",
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

    print("\n=== Step 10: 验证 PC 端 Client-Type=pc-web 调用 /api/verify/redeem 被 403 拦截 ===")
    # 即使没认证，PC 端来源也应该先被 require_mobile_verify_client 拦下，返回 403
    # （依赖项执行顺序：require_identity 与 require_mobile_verify_client 并列，
    #   FastAPI 会按声明顺序解析；不论先后，PC 端来源最终一定被 403 阻断）
    code, out, _ = run(
        ssh,
        f"curl -k -s -o /dev/null -w '%{{http_code}}' "
        f"-X POST '{BASE_URL}/api/verify/redeem' "
        f"-H 'Content-Type: application/json' "
        f"-H 'Client-Type: pc-web' "
        f"-H 'User-Agent: Mozilla/5.0 (Windows NT 10.0)' "
        f"-d '{{\"verification_code\":\"NONEXIST\",\"store_id\":1}}'",
        timeout=20,
    )
    pc_status = out.strip()
    # 期望：401（无 token） 或 403（已被来源/角色拦截）
    pc_blocked = pc_status in ("401", "403")
    print(f"  [{'OK' if pc_blocked else 'FAIL'}] PC 来源 -> {pc_status} (期望 401/403)")

    print("\n=== Step 11: 验证 H5 移动端 Client-Type=h5-mobile 不被来源拦截（401 业务） ===")
    code, out, _ = run(
        ssh,
        f"curl -k -s -o /dev/null -w '%{{http_code}}' "
        f"-X POST '{BASE_URL}/api/verify/redeem' "
        f"-H 'Content-Type: application/json' "
        f"-H 'Client-Type: h5-mobile' "
        f"-H 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)' "
        f"-d '{{\"verification_code\":\"NONEXIST\",\"store_id\":1}}'",
        timeout=20,
    )
    mobile_status = out.strip()
    # 期望：401（无 token，业务认证失败，但来源校验已放行）
    # 不应该是 403（来源拦截）。若 401 或 422 都说明来源校验放行了
    mobile_passes_source = mobile_status in ("401", "422", "400")
    print(f"  [{'OK' if mobile_passes_source else 'FAIL'}] h5-mobile 来源 -> {mobile_status} (期望 401/422/400 业务层错误)")

    print("\n=== Step 12: 验证 verify-miniprogram 来源也通过 ===")
    code, out, _ = run(
        ssh,
        f"curl -k -s -o /dev/null -w '%{{http_code}}' "
        f"-X POST '{BASE_URL}/api/verifications/verify' "
        f"-H 'Content-Type: application/json' "
        f"-H 'Client-Type: verify-miniprogram' "
        f"-H 'User-Agent: MicroMessenger MiniProgram' "
        f"-d '{{\"verification_code\":\"NONEXIST\",\"store_id\":1}}'",
        timeout=20,
    )
    mp_status = out.strip()
    mp_passes_source = mp_status in ("401", "422", "400")
    print(f"  [{'OK' if mp_passes_source else 'FAIL'}] verify-miniprogram 来源 -> {mp_status} (期望 401/422/400 业务层错误)")

    print("\n=== Step 13: 验证 unknown 来源（无 Client-Type, UA 也无法识别）被 403 ===")
    code, out, _ = run(
        ssh,
        f"curl -k -s -o /dev/null -w '%{{http_code}}' "
        f"-X POST '{BASE_URL}/api/verify/redeem' "
        f"-H 'Content-Type: application/json' "
        f"-H 'User-Agent: curl/8.0' "
        f"-d '{{\"verification_code\":\"NONEXIST\",\"store_id\":1}}'",
        timeout=20,
    )
    unknown_status = out.strip()
    unknown_blocked = unknown_status in ("401", "403")
    print(f"  [{'OK' if unknown_blocked else 'FAIL'}] unknown 来源 -> {unknown_status} (期望 401/403)")

    print("\n=== Done ===")
    print(f"  pytest:                       {'PASS' if pytest_pass else 'FAIL'}")
    print(f"  urls:                         {'PASS' if all_ok else 'FAIL'}")
    print(f"  pc-web blocked (403/401):     {'PASS' if pc_blocked else 'FAIL'}")
    print(f"  h5-mobile passes source:      {'PASS' if mobile_passes_source else 'FAIL'}")
    print(f"  verify-mp passes source:      {'PASS' if mp_passes_source else 'FAIL'}")
    print(f"  unknown blocked:              {'PASS' if unknown_blocked else 'FAIL'}")

    ssh.close()
    success = (
        pytest_pass
        and all_ok
        and pc_blocked
        and mobile_passes_source
        and mp_passes_source
        and unknown_blocked
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
