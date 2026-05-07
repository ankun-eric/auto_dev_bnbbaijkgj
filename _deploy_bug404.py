"""[BUG-FIX-MERCHANT-RESCHEDULE-V1 2026-05-07] 部署脚本：商家 H5 端「调整预约时间」抽屉化修复

部署内容：
- backend: app/api/merchant.py（detail 接口补 appointment_mode + adjust 接口加固校验/分支）
- backend tests: tests/test_bugfix_merchant_reschedule_v1.py
- h5-web: app/merchant/m/orders/[id]/page.tsx（替换 Dialog 为 Popup 抽屉）
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

        print("\n========== Step 1: 上传后端文件 ==========")
        backend_files = [
            ("backend/app/api/merchant.py",
             f"{PROJ_DIR}/backend/app/api/merchant.py"),
            ("backend/tests/test_bugfix_merchant_reschedule_v1.py",
             f"{PROJ_DIR}/backend/tests/test_bugfix_merchant_reschedule_v1.py"),
        ]
        for local, remote in backend_files:
            upload(c, local, remote)

        print("\n========== Step 2: docker cp 后端代码到容器 ==========")
        for local, _ in backend_files:
            in_container = "/app/" + local.split("/", 1)[1]
            run(c, f"docker cp {PROJ_DIR}/{local} {BACKEND}:{in_container}")

        print("\n========== Step 3: 重启 backend 容器 ==========")
        run(c, f"docker restart {BACKEND}")
        time.sleep(6)

        print("\n========== Step 4: 验证 backend 健康 ==========")
        run(
            c,
            f"curl -s -o /dev/null -w 'health=%{{http_code}}\\n' "
            f"'https://newbb.test.bangbangvip.com/autodev/{DID}/api/health' || true",
        )

        print("\n========== Step 5: 上传 h5-web 文件 ==========")
        h5_files = [
            ("h5-web/src/app/merchant/m/orders/[id]/page.tsx",
             f"{PROJ_DIR}/h5-web/src/app/merchant/m/orders/[id]/page.tsx"),
        ]
        for local, remote in h5_files:
            upload(c, local, remote)

        print("\n========== Step 6: 重建 h5-web 容器 ==========")
        run(c, f"cd {PROJ_DIR} && docker compose build h5-web 2>&1 | tail -50", timeout=1800)
        run(c, f"cd {PROJ_DIR} && docker compose up -d h5-web 2>&1 | tail -10")

        print("\n========== Step 7: 等待 h5-web 启动 ==========")
        time.sleep(8)
        run(c, f"docker ps --filter name={DID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        print("\n========== Step 8: 站点冒烟 ==========")
        for path in ["/", "/api/health", "/merchant/m/", "/api/system/server-time"]:
            run(
                c,
                f"curl -s -o /dev/null -w '{path}=%{{http_code}}\\n' "
                f"'https://newbb.test.bangbangvip.com/autodev/{DID}{path}'",
            )

        print("\n========== Step 9: 容器内运行本次新增测试 ==========")
        run(
            c,
            f"docker exec {BACKEND} sh -c 'cd /app && python -m pytest tests/test_bugfix_merchant_reschedule_v1.py -v 2>&1 | tail -120'",
            timeout=900,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
