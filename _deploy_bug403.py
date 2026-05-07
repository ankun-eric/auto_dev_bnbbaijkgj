"""[BUG-FIX-RESCHEDULE-V2 2026-05-07] 部署脚本：改约过去时段过滤 + 双重身份500 修复

部署内容：
- backend: 新增 api/system.py、强化 utils/client_source.py、强化 api/unified_orders.py、main.py 注册新 router
- backend tests: 新增 tests/test_bugfix_reschedule_v2.py
- h5-web: 新增 lib/server-time.ts、修改 app/unified-order/[id]/page.tsx
- miniprogram: 新增 utils/server-time.js、修改 pages/unified-order-detail/{index.js,wxml,wxss}
- flutter: 新增 services/server_time_service.dart、修改 screens/order/unified_order_detail_screen.dart
"""
from __future__ import annotations

import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DID}"
BACKEND = f"{DID}-backend"
H5WEB = f"{DID}-h5-web"


def make_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=900):
    print(f"\n>>> {cmd}", flush=True)
    chan = c.get_transport().open_session()
    chan.settimeout(timeout)
    chan.get_pty()
    chan.exec_command(cmd)
    last = time.time()
    out_buf = b""
    while True:
        if chan.recv_ready():
            d = chan.recv(65535)
            out_buf += d
            try:
                print(d.decode("utf-8", errors="ignore"), end="", flush=True)
            except Exception:
                pass
            last = time.time()
        if chan.exit_status_ready() and not chan.recv_ready():
            break
        if time.time() - last > timeout:
            print("\n[TIMEOUT]")
            break
        time.sleep(0.4)
    rc = chan.recv_exit_status()
    print(f"\n[rc={rc}]", flush=True)
    return rc, out_buf.decode("utf-8", errors="ignore")


def upload(c, local, remote):
    print(f"[SFTP] {local} -> {remote}")
    sftp = c.open_sftp()
    try:
        # 自动创建远端目录
        remote_dir = "/".join(remote.split("/")[:-1])
        try:
            sftp.stat(remote_dir)
        except IOError:
            run(c, f"mkdir -p {remote_dir}")
        sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    c = make_client()
    try:
        run(c, f"cd {PROJ_DIR} && git log -1 --oneline")

        print("\n========== Step 1: 上传后端文件 ==========")
        backend_files = [
            ("backend/app/api/system.py",
             f"{PROJ_DIR}/backend/app/api/system.py"),
            ("backend/app/api/unified_orders.py",
             f"{PROJ_DIR}/backend/app/api/unified_orders.py"),
            ("backend/app/utils/client_source.py",
             f"{PROJ_DIR}/backend/app/utils/client_source.py"),
            ("backend/app/main.py",
             f"{PROJ_DIR}/backend/app/main.py"),
            ("backend/tests/test_bugfix_reschedule_v2.py",
             f"{PROJ_DIR}/backend/tests/test_bugfix_reschedule_v2.py"),
        ]
        for local, remote in backend_files:
            upload(c, local, remote)

        print("\n========== Step 2: docker cp 后端代码到容器 ==========")
        # docker cp src + restart backend
        for local, _ in backend_files:
            in_container = "/app/" + local.split("/", 1)[1]
            run(c, f"docker cp {PROJ_DIR}/{local} {BACKEND}:{in_container}")

        print("\n========== Step 3: 重启 backend 容器 ==========")
        run(c, f"docker restart {BACKEND}")
        time.sleep(6)

        print("\n========== Step 4: 验证 backend 健康（含新接口） ==========")
        run(
            c,
            f"curl -s -o /dev/null -w 'health=%{{http_code}}\\n' "
            f"'https://newbb.test.bangbangvip.com/autodev/{DID}/api/health' || true",
        )
        run(
            c,
            f"curl -s -w '\\nstatus=%{{http_code}}\\n' "
            f"'https://newbb.test.bangbangvip.com/autodev/{DID}/api/system/server-time'",
        )

        print("\n========== Step 5: 上传 h5-web 文件 ==========")
        h5_files = [
            ("h5-web/src/lib/server-time.ts",
             f"{PROJ_DIR}/h5-web/src/lib/server-time.ts"),
            ("h5-web/src/app/unified-order/[id]/page.tsx",
             f"{PROJ_DIR}/h5-web/src/app/unified-order/[id]/page.tsx"),
        ]
        for local, remote in h5_files:
            upload(c, local, remote)

        print("\n========== Step 6: 重建 h5-web 容器 ==========")
        run(c, f"cd {PROJ_DIR} && docker compose build h5-web 2>&1 | tail -50", timeout=1800)
        run(c, f"cd {PROJ_DIR} && docker compose up -d h5-web 2>&1 | tail -10")

        print("\n========== Step 7: 上传小程序文件（仅静态托管，无需重启容器） ==========")
        mp_files = [
            ("miniprogram/utils/server-time.js",
             f"{PROJ_DIR}/miniprogram/utils/server-time.js"),
            ("miniprogram/pages/unified-order-detail/index.js",
             f"{PROJ_DIR}/miniprogram/pages/unified-order-detail/index.js"),
            ("miniprogram/pages/unified-order-detail/index.wxml",
             f"{PROJ_DIR}/miniprogram/pages/unified-order-detail/index.wxml"),
            ("miniprogram/pages/unified-order-detail/index.wxss",
             f"{PROJ_DIR}/miniprogram/pages/unified-order-detail/index.wxss"),
        ]
        for local, remote in mp_files:
            upload(c, local, remote)

        print("\n========== Step 8: 上传 Flutter 文件（仅源代码同步，APP 端打包另行处理） ==========")
        flutter_files = [
            ("flutter_app/lib/services/server_time_service.dart",
             f"{PROJ_DIR}/flutter_app/lib/services/server_time_service.dart"),
            ("flutter_app/lib/screens/order/unified_order_detail_screen.dart",
             f"{PROJ_DIR}/flutter_app/lib/screens/order/unified_order_detail_screen.dart"),
        ]
        for local, remote in flutter_files:
            upload(c, local, remote)

        print("\n========== Step 9: 等待 h5-web 启动 ==========")
        time.sleep(8)
        run(c, f"docker ps --filter name={DID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        print("\n========== Step 10: 站点冒烟 ==========")
        for path in ["/", "/api/health", "/api/system/server-time"]:
            run(
                c,
                f"curl -s -o /dev/null -w '{path}=%{{http_code}}\\n' "
                f"'https://newbb.test.bangbangvip.com/autodev/{DID}{path}'",
            )

        print("\n========== Step 11: 容器内运行 v2 测试 ==========")
        run(
            c,
            f"docker exec {BACKEND} sh -c 'cd /app && python -m pytest tests/test_bugfix_reschedule_v2.py -v 2>&1 | tail -80'",
            timeout=900,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
