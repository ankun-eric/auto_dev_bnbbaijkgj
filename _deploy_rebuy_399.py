"""[BUG-FIX-REBUY-V1 2026-05-07]「再来一单」跳转页面错误 Bug 修复部署脚本

本次改动文件：
- backend/app/api/unified_orders.py     (新增 POST /reorder 接口 + 引入 ProductSku)
- backend/tests/test_reorder_bug_fix_v1.py (新建 8 用例)
- h5-web/src/app/unified-orders/page.tsx  (列表页：改 rebuy 按钮 + handleRebuy)
- h5-web/src/app/unified-order/[id]/page.tsx (详情页：新增「再来一单」按钮 + handleRebuy)
- miniprogram/pages/unified-orders/index.js / .wxml (列表加按钮 + onRebuy)
- miniprogram/pages/unified-order-detail/index.js / .wxml (详情加按钮 + onRebuy)
- flutter_app/lib/services/api_service.dart (reorderUnifiedOrder)
- flutter_app/lib/screens/order/unified_orders_screen.dart (列表加按钮 + _onRebuy)
- flutter_app/lib/screens/order/unified_order_detail_screen.dart (详情加按钮 + _onRebuy)

部署流程：SFTP 上传 → docker build backend + h5-web → up -d → gateway reload →
           容器内 pytest test_reorder_bug_fix_v1.py → HTTPS smoke
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
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES = [
    # 后端
    "backend/app/api/unified_orders.py",
    "backend/tests/test_reorder_bug_fix_v1.py",
    # H5 端
    "h5-web/src/app/unified-orders/page.tsx",
    "h5-web/src/app/unified-order/[id]/page.tsx",
    # 小程序（先上传到服务器，后续打包用）
    "miniprogram/pages/unified-orders/index.js",
    "miniprogram/pages/unified-orders/index.wxml",
    "miniprogram/pages/unified-order-detail/index.js",
    "miniprogram/pages/unified-order-detail/index.wxml",
    # Flutter 端
    "flutter_app/lib/services/api_service.dart",
    "flutter_app/lib/screens/order/unified_orders_screen.dart",
    "flutter_app/lib/screens/order/unified_order_detail_screen.dart",
]


def exec_cmd(client: paramiko.SSHClient, cmd: str, timeout: int = 600):
    print(f"[exec] {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err and code != 0:
        print("[stderr]", err[-2000:])
    return code, out, err


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    client.connect(
        HOST, port=22, username=USER, password=PASSWORD,
        timeout=30, banner_timeout=30, auth_timeout=30,
    )
    sftp = client.open_sftp()

    repo_root = Path(__file__).resolve().parent
    print(f"\n=== SFTP 上传 ===  repo={repo_root}")
    for rel in FILES:
        local = repo_root / rel
        remote = f"{PROJECT_DIR}/{rel}".replace("\\", "/")
        if not local.exists():
            print(f"  - SKIP missing: {local}")
            continue
        remote_dir = "/".join(remote.split("/")[:-1])
        exec_cmd(client, f"mkdir -p '{remote_dir}'")
        print(f"  ↑ {rel}  ({local.stat().st_size} bytes)")
        sftp.put(str(local), remote)
    sftp.close()

    # backend rebuild
    print("\n=== docker compose build backend ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose build backend 2>&1 | tail -100",
        timeout=900,
    )
    if rc != 0:
        print("[fail] backend build 失败")
        client.close()
        return 1

    # h5-web rebuild
    print("\n=== docker compose build h5-web ===")
    rc, _, _ = exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -200",
        timeout=1500,
    )
    if rc != 0:
        print("[fail] h5-web build 失败")
        client.close()
        return 1

    # up -d
    print("\n=== docker compose up -d --force-recreate h5-web backend ===")
    exec_cmd(
        client,
        f"cd {PROJECT_DIR} && docker compose up -d --force-recreate h5-web backend 2>&1 | tail -80",
        timeout=240,
    )

    time.sleep(10)

    # gateway reload
    print("\n=== gateway nginx reload ===")
    exec_cmd(client, "docker exec gateway nginx -t 2>&1 | tail -10", timeout=30)
    exec_cmd(client, "docker exec gateway nginx -s reload 2>&1 | tail -10", timeout=30)

    # 容器内 pytest（reorder 8 用例）
    print("\n=== 容器内 pytest test_reorder_bug_fix_v1.py ===")
    container = f"{DEPLOY_ID}-backend"
    rc_pytest, pytest_out, _ = exec_cmd(
        client,
        f"docker exec {container} python -m pytest tests/test_reorder_bug_fix_v1.py -v 2>&1 | tail -120",
        timeout=240,
    )

    # HTTPS smoke
    print("\n=== HTTPS smoke ===")
    urls = [
        (f"{BASE_URL}/", "200|3"),
        (f"{BASE_URL}/unified-orders/", "200|3"),
        (f"{BASE_URL}/api/openapi.json", "200"),
        # reorder 接口需鉴权 → 期望 401/403
        (f"{BASE_URL}/api/orders/unified/1/reorder", "auth_required"),
    ]
    smoke_pass = True
    fails = []
    for u, expected in urls:
        # reorder 是 POST 请求
        method = "-X POST" if "/reorder" in u else ""
        rc, out, err = exec_cmd(
            client,
            f"curl -k -s {method} -o /dev/null -w '%{{http_code}}' '{u}'",
            timeout=20,
        )
        code = (out or "").strip()
        if expected == "200":
            ok = code == "200"
        elif expected == "200|3":
            ok = code in ("200", "301", "302", "303", "307", "308")
        elif expected == "auth_required":
            ok = code in ("401", "403", "422")
        else:
            ok = False
        marker = "OK  " if ok else "FAIL"
        print(f"  [{marker}] {u} -> {code} (expect {expected})")
        if not ok:
            smoke_pass = False
            fails.append((u, code, expected))

    # 容器内确认 H5 chunks 含 reorder 关键 token（再来一单 已存在于产物中）
    print("\n=== 容器内 H5 chunks 关键 token 检查（reorder API 调用） ===")
    h5_container = f"{DEPLOY_ID}-h5-web"
    for token, label in [
        ("/reorder", "reorder 接口路径"),
        ("from_rebuy", "from_rebuy 标记参数"),
    ]:
        exec_cmd(
            client,
            f"docker exec {h5_container} sh -lc \"grep -rl '{token}' /app/.next/static/chunks/ 2>/dev/null | head -3 || echo NOT_FOUND_{label}\"",
            timeout=30,
        )

    pytest_pass = "passed" in pytest_out and "failed" not in pytest_out and "error" not in pytest_out.lower()
    # 简化判断：寻找形如 "8 passed"
    import re as _re
    m = _re.search(r"(\d+)\s+passed", pytest_out or "")
    if m and int(m.group(1)) >= 8 and "failed" not in pytest_out:
        pytest_pass = True
    else:
        pytest_pass = False

    client.close()
    print("\n=== 部署完成 ===")
    print(f"smoke_pass={smoke_pass}  pytest_pass={pytest_pass}")
    if fails:
        print("FAILED URLS:")
        for u, c, e in fails:
            print(f"  {u}  got={c} expect={e}")
    return 0 if (smoke_pass and pytest_pass) else 2


if __name__ == "__main__":
    sys.exit(main())
