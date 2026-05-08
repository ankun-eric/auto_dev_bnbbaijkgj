"""[BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v1.0] 部署脚本

变更内容（前端三端 + 后端测试）：
- h5-web:
  * src/app/unified-order/[id]/page.tsx（改约成功立即关弹窗 + 区分文案 + 写列表刷新标志）
  * src/app/unified-orders/page.tsx（监听 pageshow / visibilitychange / focus 触发刷新）
- miniprogram:
  * pages/unified-order-detail/index.js（弹窗自动关 + 区分文案 + 写 globalData 标志）
  * pages/unified-orders/index.js（onShow 检测 globalData 标志 → 强制刷新）
  * app.js（globalData.unifiedOrdersNeedRefresh 字段）
- flutter_app:
  * lib/utils/unified_orders_refresh_notifier.dart（新文件 - 全局信号器）
  * lib/screens/order/unified_order_detail_screen.dart（改约成功通知 + 区分文案）
  * lib/screens/order/unified_orders_screen.dart（监听信号器自动刷新）
- backend:
  * tests/test_bugfix_reschedule_popup_auto_close.py（4 个回归用例）

部署动作：
1) 上传 h5-web + miniprogram + flutter_app + backend 测试文件到服务器
2) docker cp 后端测试到容器
3) 重启 backend（无需，仅新增测试不需要重启）
4) docker compose build h5-web + up -d
5) 远程 smoke：/api/health, /, /api/orders/unified（401 也算正常）
6) 容器内 pytest tests/test_bugfix_reschedule_popup_auto_close.py
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

        print("\n========== Step 1: 上传 h5-web 改动 ==========")
        h5_files = [
            ("h5-web/src/app/unified-order/[id]/page.tsx",
             f"{PROJ_DIR}/h5-web/src/app/unified-order/[id]/page.tsx"),
            ("h5-web/src/app/unified-orders/page.tsx",
             f"{PROJ_DIR}/h5-web/src/app/unified-orders/page.tsx"),
        ]
        for local, remote in h5_files:
            upload(c, local, remote)

        print("\n========== Step 2: 上传后端测试文件 ==========")
        backend_files = [
            ("backend/tests/test_bugfix_reschedule_popup_auto_close.py",
             f"{PROJ_DIR}/backend/tests/test_bugfix_reschedule_popup_auto_close.py"),
        ]
        for local, remote in backend_files:
            upload(c, local, remote)

        print("\n========== Step 3: docker cp 后端测试到容器 ==========")
        for local, _ in backend_files:
            in_container = "/app/" + local.split("/", 1)[1]
            run(c, f"docker cp {PROJ_DIR}/{local} {BACKEND}:{in_container}")

        print("\n========== Step 4: 重建 h5-web 容器 ==========")
        run(c, f"cd {PROJ_DIR} && docker compose build h5-web 2>&1 | tail -50", timeout=1800)
        run(c, f"cd {PROJ_DIR} && docker compose up -d h5-web 2>&1 | tail -10")

        print("\n========== Step 5: 等待 h5-web 启动 ==========")
        time.sleep(10)
        run(c, f"docker ps --filter name={DID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        print("\n========== Step 6: 站点冒烟 ==========")
        for path in ["/", "/api/health"]:
            run(
                c,
                f"curl -s -o /dev/null -w '{path}=%{{http_code}}\\n' "
                f"'https://newbb.test.bangbangvip.com/autodev/{DID}{path}'",
            )

        print("\n========== Step 7: 容器内运行新增测试 ==========")
        run(
            c,
            f"docker exec {BACKEND} sh -c 'cd /app && python -m pytest "
            f"tests/test_bugfix_reschedule_popup_auto_close.py -v 2>&1 | tail -120'",
            timeout=900,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
