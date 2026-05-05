#!/usr/bin/env python3
"""[Bugfix 2026-05-05] 营业时间下拉去重 + 改约按钮文案统一 — 部署脚本

变更：
  Bug 1：admin-web/h5-web 门店编辑页 BUSINESS_END_OPTIONS 移除多余 push 22:00
  Bug 2：H5/小程序/Flutter 三端订单列表+详情 改约按钮文案统一为「改约」

策略：paramiko SCP 上传变更文件 → docker compose build → up → 验证
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"
ADMIN_NAME = f"{PROJECT_ID}-admin-web"
H5_NAME = f"{PROJECT_ID}-h5-web"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"

LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

# 变更文件清单
FILES_TO_UPLOAD: list[tuple[str, str]] = [
    # admin-web — Bug 1
    (
        "admin-web/src/app/(admin)/merchant/stores/page.tsx",
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/merchant/stores/page.tsx",
    ),
    # h5-web — Bug 1 + Bug 2
    (
        "h5-web/src/app/merchant/store-settings/page.tsx",
        f"{PROJECT_DIR}/h5-web/src/app/merchant/store-settings/page.tsx",
    ),
    (
        "h5-web/src/app/unified-orders/page.tsx",
        f"{PROJECT_DIR}/h5-web/src/app/unified-orders/page.tsx",
    ),
    (
        "h5-web/src/app/unified-order/[id]/page.tsx",
        f"{PROJECT_DIR}/h5-web/src/app/unified-order/[id]/page.tsx",
    ),
    # 小程序与 Flutter 是客户端二进制构建产物，源码同步即可（小程序后续单独打 zip，flutter 后续单独打 APK）
    (
        "miniprogram/pages/unified-orders/index.wxml",
        f"{PROJECT_DIR}/miniprogram/pages/unified-orders/index.wxml",
    ),
    (
        "miniprogram/pages/unified-order-detail/index.wxml",
        f"{PROJECT_DIR}/miniprogram/pages/unified-order-detail/index.wxml",
    ),
    (
        "flutter_app/lib/screens/order/unified_orders_screen.dart",
        f"{PROJECT_DIR}/flutter_app/lib/screens/order/unified_orders_screen.dart",
    ),
    (
        "flutter_app/lib/screens/order/unified_order_detail_screen.dart",
        f"{PROJECT_DIR}/flutter_app/lib/screens/order/unified_order_detail_screen.dart",
    ),
]


def run(ssh, cmd, timeout=600, ignore_err=False):
    print(f"\n>>> {cmd}", flush=True)
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    print(f"[exit_code={rc}]")
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed: {cmd}\n{err}")
    return out, err, rc


def main() -> int:
    print("=" * 70)
    print("[deploy] Bugfix 营业时间去重 + 改约按钮文案统一 部署开始")
    print("=" * 70)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)

    sftp = ssh.open_sftp()
    try:
        # 1) 上传文件
        for local_rel, remote_abs in FILES_TO_UPLOAD:
            local_abs = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.isfile(local_abs):
                raise FileNotFoundError(local_abs)
            remote_dir = os.path.dirname(remote_abs)
            run(ssh, f'mkdir -p "{remote_dir}"', ignore_err=True)
            print(f"[scp] {local_abs} -> {remote_abs}", flush=True)
            sftp.put(local_abs, remote_abs)
        sftp.close()

        # 2) 验证关键变更已上传（Bug 1：BUSINESS_END_OPTIONS 不再 push 22:00）
        # 上传后服务器上文件中不应再包含 `out.push({ label: '22:00', value: '22:00' });`
        run(
            ssh,
            f"grep -c \"out.push({{ label: '22:00', value: '22:00' }})\" "
            f"{PROJECT_DIR}/admin-web/src/app/\\(admin\\)/merchant/stores/page.tsx",
            ignore_err=True,
        )
        run(
            ssh,
            f"grep -c \"out.push({{ label: '22:00', value: '22:00' }})\" "
            f"{PROJECT_DIR}/h5-web/src/app/merchant/store-settings/page.tsx",
            ignore_err=True,
        )
        # Bug 2：H5/小程序/Flutter 中不应再出现「已无法改期」
        run(
            ssh,
            f"grep -rn '已无法改期' {PROJECT_DIR}/h5-web/src "
            f"{PROJECT_DIR}/miniprogram/pages "
            f"{PROJECT_DIR}/flutter_app/lib || echo '[ok] 无残留 已无法改期'",
            ignore_err=True,
        )

        # 3) 重建 admin-web 与 h5-web（仅前端变更）
        run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose build admin-web h5-web",
            timeout=1800,
        )
        run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose up -d admin-web h5-web",
            timeout=300,
        )

        # 4) 等待启动
        print("\n[等待 25 秒，让前端容器启动稳定]", flush=True)
        time.sleep(25)

        # 5) 健康 + 关键页面连通性验证
        for label, url in [
            ("api_health", f"{BASE_URL}/api/health"),
            ("admin_login", f"{BASE_URL}/admin/login/"),
            ("admin_stores", f"{BASE_URL}/admin/merchant/stores/"),
            ("h5_orders", f"{BASE_URL}/unified-orders/"),
            ("h5_store_settings", f"{BASE_URL}/merchant/store-settings/"),
        ]:
            run(
                ssh,
                f"curl -sk -L -o /dev/null -w '{label}: %{{http_code}}\\n' {url}",
                ignore_err=True,
            )

        # 6) 在线产物校验：进容器中查看 build 后 page.tsx 已被 next 编译
        run(
            ssh,
            f"docker exec {ADMIN_NAME} sh -lc 'ls -la /app/.next 2>/dev/null | head -5 || echo no .next dir'",
            ignore_err=True,
        )
        run(
            ssh,
            f"docker exec {H5_NAME} sh -lc 'ls -la /app/.next 2>/dev/null | head -5 || echo no .next dir'",
            ignore_err=True,
        )

        print("\n" + "=" * 70)
        print("[deploy] 部署流程完成")
        print("=" * 70)
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
