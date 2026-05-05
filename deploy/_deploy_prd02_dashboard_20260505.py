"""[PRD-02 门店端预约看板（日 / 周 / 月 三视图）v1.0] 部署脚本

本次改动列表
------------
- backend/tests/test_prd02_dashboard_v1.py（新增）— 41 用例覆盖卡片字段 / 状态口径 / 9 段映射
- admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx（改动）
  · formatYuan 改为强制整数格式 `¥1280`（PRD §R-02-05）
  · 9 宫格热度色改为绿色梯度（PRD §2.2 视觉规则）
  · 空时段显示「暂无预约」（PRD §5 异常处理）
  · 抽屉「📞拨打」改为 `tel:` 唤起 + 复制兜底（PRD §2.7）
  · 视图（日/周/月）和列表偏好均写入 localStorage（PRD §R-02-04）
- admin-web/src/app/(admin)/product-system/orders/page.tsx（改动）
  · 默认进入看板，浏览器记忆为 `list` 时才停留列表页（PRD §R-02-04）
  · 切换到看板时写入 localStorage 偏好

操作步骤
--------
1. SCP 上传 3 个变更文件
2. 容器内运行新增 PRD-02 单元测试（test_prd02_dashboard_v1.py）+ 既有 PRD-01 / 看板测试
3. docker compose build admin-web → up -d admin-web
   后端无源代码改动，无需 build backend，但执行 backend test 确认未回归
4. 5 个核心 URL 健康检查（含 /api/merchant/dashboard/time-slots、/api/common/time-slots、看板页 HTML）

成功标准
--------
- 单元测试全部 PASS
- 5 个 URL 全 200/308/302
- admin-web 重建后看板页可访问
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
    ("backend/tests/test_prd02_dashboard_v1.py",
     f"{REMOTE_PROJ}/backend/tests/test_prd02_dashboard_v1.py"),
    ("admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx",
     f"{REMOTE_PROJ}/admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx"),
    ("admin-web/src/app/(admin)/product-system/orders/page.tsx",
     f"{REMOTE_PROJ}/admin-web/src/app/(admin)/product-system/orders/page.tsx"),
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

    print("\n=== Step 1.5: 把新增 test 文件 cp 进 backend 容器（容器内 tests/ 是只读 image，不会自动同步） ===")
    run(
        ssh,
        f"docker cp {REMOTE_PROJ}/backend/tests/test_prd02_dashboard_v1.py "
        f"{container_be}:/app/tests/test_prd02_dashboard_v1.py",
        timeout=60,
    )

    print("\n=== Step 2: 容器内运行 PRD-02 单元测试（不依赖 conftest，避免连库） ===")
    code, out, _ = run(
        ssh,
        f"docker exec {container_be} python -m pytest "
        f"tests/test_prd02_dashboard_v1.py "
        f"tests/test_merchant_dashboard_v1.py "
        f"tests/test_time_slots_unified_v1.py "
        f"-v --noconftest -p no:cacheprovider --tb=short 2>&1 | tail -120",
        timeout=180,
    )
    pytest_pass = ("passed" in out) and ("failed" not in out.split("=")[-1])

    print("\n=== Step 3: 重建 admin-web 容器（包含 Next.js 构建） ===")
    code, _, _ = run(
        ssh,
        f"cd {REMOTE_PROJ} && docker compose build admin-web 2>&1 | tail -60",
        timeout=1800,
    )
    if code != 0:
        print("[FAIL] admin-web build failed")
        ssh.close()
        return 1

    print("\n=== Step 4: docker compose up -d admin-web ===")
    run(ssh, f"cd {REMOTE_PROJ} && docker compose up -d admin-web 2>&1 | tail -10")

    print("\n=== Step 5: 等待 admin-web 启动 ===")
    time.sleep(10)

    print("\n=== Step 6: 核心 URL 健康检查 ===")
    urls = [
        f"{BASE_URL}/api/health",
        f"{BASE_URL}/admin/login/",
        f"{BASE_URL}/admin/product-system/orders/dashboard/",
        f"{BASE_URL}/admin/product-system/orders/",
        f"{BASE_URL}/api/merchant/dashboard/time-slots",
        f"{BASE_URL}/api/common/time-slots",
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

    print("\n=== Done ===")
    print(f"  pytest:    {'PASS' if pytest_pass else 'FAIL'}")
    print(f"  urls:      {'PASS' if all_ok else 'FAIL'}")

    ssh.close()
    success = pytest_pass and all_ok
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
