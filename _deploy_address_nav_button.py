"""[2026-05-05 订单页地址导航按钮 PRD v1.0] 部署脚本

本次涉及：
- 后端 OrderResponse 增加 store_address/store_lat/store_lng/shipping_address_text/
  shipping_address_name/shipping_address_phone 字段透传（_build_order_response）
- H5 端 checkout / unified-order/[id] 增加导航按钮 + 通用 AddressNavButton 组件
- 小程序端 checkout / unified-order-detail 增加导航按钮 + utils/map-nav.js
- Flutter App 端 checkout / unified-order detail 增加导航按钮 + widgets/address_nav_button.dart

执行步骤：
1) SFTP 上传 backend + h5-web 变更（小程序与 Flutter 不部署到 H5 服务器，由打包阶段独立分发）
2) docker compose build h5-web backend（仅这两个）
3) docker compose up -d h5-web backend
4) 等服务启动 30s
5) curl 验证关键 URL 可达
"""
from __future__ import annotations

import os
import sys
import time
import posixpath

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

FILES_TO_UPLOAD = [
    # ===== 后端：schema + _build_order_response =====
    "backend/app/schemas/unified_orders.py",
    "backend/app/api/unified_orders.py",
    # ===== H5: 新增组件 + 修改 MapNavSheet + 修改两个页面 =====
    "h5-web/src/components/AddressNavButton.tsx",
    "h5-web/src/components/MapNavSheet.tsx",
    "h5-web/src/app/checkout/page.tsx",
    "h5-web/src/app/unified-order/[id]/page.tsx",
    # ===== 小程序（同步源码到服务器仓库，便于版本溯源） =====
    "miniprogram/utils/map-nav.js",
    "miniprogram/pages/checkout/index.js",
    "miniprogram/pages/checkout/index.wxml",
    "miniprogram/pages/checkout/index.wxss",
    "miniprogram/pages/unified-order-detail/index.js",
    "miniprogram/pages/unified-order-detail/index.wxml",
    "miniprogram/pages/unified-order-detail/index.wxss",
    # ===== Flutter（同步源码到服务器仓库） =====
    "flutter_app/lib/widgets/address_nav_button.dart",
    "flutter_app/lib/utils/map_nav_util.dart",
    "flutter_app/lib/models/unified_order.dart",
    "flutter_app/lib/screens/product/checkout_screen.dart",
    "flutter_app/lib/screens/order/unified_order_detail_screen.dart",
    # ===== 自动化测试 =====
    "tests/test_address_nav_button_v1.py",
]


def log(msg: str) -> None:
    print(f"[deploy_addr_nav] {msg}", flush=True)


def make_ssh() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    log(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        snippet = out if len(out) < 4000 else out[:2000] + "\n...[truncated]...\n" + out[-2000:]
        log(f"stdout:\n{snippet}")
    if err:
        snippet = err if len(err) < 4000 else err[:2000] + "\n...[truncated]...\n" + err[-2000:]
        log(f"stderr:\n{snippet}")
    log(f"exit code: {code}")
    return code, out, err


def sftp_upload(sftp: paramiko.SFTPClient, local: str, remote: str) -> None:
    parts = remote.split("/")
    cur = ""
    for p in parts[:-1]:
        if not p:
            cur = "/"
            continue
        cur = posixpath.join(cur, p) if cur else "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)
    sftp.put(local, remote)
    log(f"uploaded: {local} -> {remote}")


def main() -> int:
    ssh = make_ssh()
    try:
        sftp = ssh.open_sftp()
        try:
            log("== Step 1: SFTP upload changed files ==")
            uploaded = 0
            for rel in FILES_TO_UPLOAD:
                local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
                if not os.path.exists(local):
                    log(f"WARN: local file missing: {local}")
                    continue
                remote = posixpath.join(REMOTE_DIR, rel)
                sftp_upload(sftp, local, remote)
                uploaded += 1
            log(f"== uploaded {uploaded} files ==")
        finally:
            sftp.close()

        log("== Step 2: docker compose build h5-web backend ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose build h5-web backend 2>&1 | tail -200",
            timeout=2400,
        )
        if rc != 0:
            log("ERROR: docker compose build failed")
            return 1

        log("== Step 3: docker compose up -d h5-web backend ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose up -d h5-web backend 2>&1 | tail -50",
            timeout=600,
        )
        if rc != 0:
            log("ERROR: docker compose up failed")
            return 1

        log("== Step 4: wait services to be ready (30s) ==")
        time.sleep(30)

        log("== Step 5: external URL accessibility checks ==")
        url_checks = [
            (f"{PROJECT_BASE_URL}/", "200|301|302|307|308"),
            (f"{PROJECT_BASE_URL}/api/health", "200"),
            (f"{PROJECT_BASE_URL}/checkout", "200|301|302|307|308"),
            (f"{PROJECT_BASE_URL}/unified-orders", "200|301|302|307|308"),
            (f"{PROJECT_BASE_URL}/login", "200|301|302|307|308"),
        ]
        all_ok = True
        for url, expect in url_checks:
            rc, out, err = run(
                ssh,
                f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'",
                timeout=30,
            )
            code_str = (out or "").strip()
            if code_str in expect.split("|"):
                log(f"OK   {code_str:>4}  {url}")
            else:
                log(f"FAIL {code_str:>4} (expect {expect})  {url}")
                all_ok = False

        log("== Step 6: 后端 OpenAPI Schema 字段验证 ==")
        # 通过 /openapi.json 检查新增字段已暴露
        rc, out, err = run(
            ssh,
            f"curl -s --max-time 15 '{PROJECT_BASE_URL}/api/openapi.json' "
            f"| python3 -c \"import json,sys;"
            f"d=json.load(sys.stdin);"
            f"r=d.get('components',{{}}).get('schemas',{{}}).get('UnifiedOrderResponse',{{}}).get('properties',{{}});"
            f"print('store_address' in r, 'store_lat' in r, 'shipping_address_text' in r);\" "
            f"2>&1 | tail -5",
            timeout=30,
        )
        out_l = (out or "").strip()
        if "True True True" in out_l:
            log("OK: OpenAPI schema 已含新增字段 store_address / store_lat / shipping_address_text")
        else:
            log(f"WARN: OpenAPI schema 检测异常: {out_l}")

        if not all_ok:
            log("== Deploy DONE (有部分失败) ==")
            return 4

        log("== Deploy DONE ==")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
