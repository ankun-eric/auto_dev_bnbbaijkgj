"""[订单详情页订单地址展示统一 Bug 修复 v1.0] 多服务联合部署。

本次涉及变更：
  - backend                 ：unified_orders.py / product_admin.py / schemas/unified_orders.py
  - h5-web                  ：unified-order/[id]/page.tsx
  - admin-web               ：product-system/orders/page.tsx
  - miniprogram             ：unified-order-detail (wxml + js) — 仅打包，不依赖服务器
  - flutter_app             ：models/unified_order.dart + screens/order/unified_order_detail_screen.dart
                              — 仅源码同步（不重新出 APK/IPA）

部署步骤：
  1. SFTP 上传变更文件
  2. docker compose build backend admin-web h5-web
  3. docker compose up -d backend admin-web h5-web
  4. 等待容器健康，重新挂 gateway-nginx 网络
  5. curl 验证关键 URL
"""
from __future__ import annotations

import os
import sys
import time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{PROJECT_ID}'
GATEWAY = 'gateway-nginx'
COMPOSE_FILE = 'docker-compose.yml'
BASE_URL = f'https://{HOST}/autodev/{PROJECT_ID}'

LOCAL_ROOT = r'C:\auto_output\bnbbaijkgj'

# 上传至服务器的变更文件清单（路径相对仓库根）
CHANGED_FILES = [
    # --- 后端 ---
    'backend/app/api/unified_orders.py',
    'backend/app/api/product_admin.py',
    'backend/app/schemas/unified_orders.py',
    # --- H5 ---
    'h5-web/src/app/unified-order/[id]/page.tsx',
    # --- Admin Web ---
    'admin-web/src/app/(admin)/product-system/orders/page.tsx',
    # --- 小程序（仅同步源码，便于在服务器上分发 zip 包，开发者扫码体验） ---
    'miniprogram/pages/unified-order-detail/index.wxml',
    'miniprogram/pages/unified-order-detail/index.js',
    # --- Flutter（仅同步源码，APK/IPA 走单独的打包脚本） ---
    'flutter_app/lib/models/unified_order.dart',
    'flutter_app/lib/screens/order/unified_order_detail_screen.dart',
]

# 需要在服务端 docker compose build / up 的服务
REBUILD_SERVICES = ['backend', 'admin-web', 'h5-web']
CONTAINER_NAME_MAP = {
    'backend': f'{PROJECT_ID}-backend',
    'admin-web': f'{PROJECT_ID}-admin-web',
    'h5-web': f'{PROJECT_ID}-h5',
}

# 部署后健康验证 URL
VERIFY_URLS = [
    f'{BASE_URL}/api/health',
    f'{BASE_URL}/',
    f'{BASE_URL}/login',
    f'{BASE_URL}/admin/login',
]


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=600, ignore_error=False):
    print(f"\n>>> {cmd}", flush=True)
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out_chunks = []
    while True:
        if chan.recv_ready():
            data = chan.recv(8192).decode('utf-8', errors='replace')
            sys.stdout.write(data)
            sys.stdout.flush()
            out_chunks.append(data)
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(8192).decode('utf-8', errors='replace')
            sys.stdout.write(data)
            sys.stdout.flush()
            out_chunks.append(data)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"\n[exit={code}]", flush=True)
    if code != 0 and not ignore_error:
        print(f"!! 命令失败: {cmd}")
    return code, ''.join(out_chunks)


def upload_files(ssh):
    sftp = ssh.open_sftp()
    try:
        for rel in CHANGED_FILES:
            local = os.path.join(LOCAL_ROOT, rel.replace('/', os.sep))
            if not os.path.exists(local):
                print(f"[skip] 本地文件不存在: {local}")
                continue
            remote = f'{PROJECT_DIR}/{rel}'
            remote_dir = os.path.dirname(remote)
            run(ssh, f'mkdir -p "{remote_dir}"', ignore_error=True)
            print(f"[SFTP] {local} -> {remote}", flush=True)
            sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    ssh = get_ssh()
    try:
        # 1) 上传变更文件
        upload_files(ssh)

        # 2) 文件 sanity check
        run(ssh,
            f'cd {PROJECT_DIR} && '
            f'grep -c "order_address_type" backend/app/api/unified_orders.py && '
            f'grep -c "order_address_type" h5-web/src/app/unified-order/\\[id\\]/page.tsx && '
            f'grep -c "order_address_type" admin-web/src/app/\\(admin\\)/product-system/orders/page.tsx',
            ignore_error=True)

        # 3) 重建相关服务（顺序：backend → admin-web → h5-web）
        for svc in REBUILD_SERVICES:
            run(ssh,
                f'cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build {svc}',
                timeout=1800)

        # 4) 启动新容器
        for svc in REBUILD_SERVICES:
            run(ssh,
                f'cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d {svc}',
                timeout=300)

        # 5) 重新挂 gateway 网络（避免 502）
        run(ssh,
            f'docker network connect {PROJECT_ID}-network {GATEWAY} 2>/dev/null || true',
            ignore_error=True)
        run(ssh, f'docker exec {GATEWAY} nginx -s reload', ignore_error=True)

        # 6) 健康等待
        for svc, container in CONTAINER_NAME_MAP.items():
            ok = False
            for i in range(20):
                code, out = run(ssh,
                    f'docker ps --filter name={container} --format "{{{{.Status}}}}"',
                    timeout=20, ignore_error=True)
                status = out.strip()
                if status.startswith('Up'):
                    print(f"[wait #{i+1}] {container} 已运行: {status!r}")
                    ok = True
                    break
                print(f"[wait #{i+1}] {container} status={status!r}")
                time.sleep(5)
            if not ok:
                print(f"!! 容器 {container} 100s 内未起来")

        # 7) 验证关键 URL
        print("\n=== HTTP 验证 ===")
        results = {}
        for url in VERIFY_URLS:
            code, out = run(ssh,
                f'curl -s -o /dev/null -w "%{{http_code}}" -L --max-time 15 "{url}"',
                timeout=30, ignore_error=True)
            results[url] = out.strip()

        # 8) 容器最终状态
        run(ssh,
            f'docker ps --format "table {{{{.Names}}}}\t{{{{.Status}}}}" '
            f'--filter name={PROJECT_ID}')

        # 9) 总结
        print("\n=========================================")
        print(" 部署结果汇总")
        print("=========================================")
        for url, code in results.items():
            print(f"  {code}  {url}")
        print("=========================================")

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
