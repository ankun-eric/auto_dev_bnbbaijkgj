#!/usr/bin/env python3
"""[H5 支付 Bug 修复方案 v1.0] 增量部署 + 容器内 pytest

修复内容（PRD `H5 支付 BUG 修复方案文档`）：
- H5：新增标准支付成功页 /pay/success（PRD §3 标准版 UI/交互）
- H5：checkout / sandbox-pay / unified-order 三处支付成功跳转改为 /pay/success
- 后端：新增 test_h5_pay_success_bugfix.py 8 用例（pay_success 必备字段透出 +
        confirm-free 完整链路 + 鉴权防伪造）
"""
import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    # H5 新增标准支付成功页
    ("h5-web/src/app/pay/success/page.tsx",
     "h5-web/src/app/pay/success/page.tsx"),
    # H5 三处跳转改造
    ("h5-web/src/app/checkout/page.tsx", "h5-web/src/app/checkout/page.tsx"),
    ("h5-web/src/app/sandbox-pay/page.tsx", "h5-web/src/app/sandbox-pay/page.tsx"),
    ("h5-web/src/app/unified-order/[id]/page.tsx",
     "h5-web/src/app/unified-order/[id]/page.tsx"),
    # 后端测试新增（不改业务代码，仅补充覆盖 PRD §3 + §B5）
    ("backend/tests/test_h5_pay_success_bugfix.py",
     "backend/tests/test_h5_pay_success_bugfix.py"),
]


def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    return c


def run(c, cmd, timeout=900):
    print(f"\n>>> {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-3500:])
    if err:
        print("STDERR:", err[-1500:])
    print(f"--- EXIT {rc} ---")
    return rc, out, err


def upload(sftp, local, remote):
    parts = remote.split("/")
    d = ""
    for p in parts[:-1]:
        if not p:
            continue
        d = d + "/" + p
        try:
            sftp.stat(d)
        except IOError:
            try:
                sftp.mkdir(d)
            except IOError:
                pass
    print(f"  upload: {local}  ->  {remote}")
    sftp.put(local, remote)


def main():
    c = make_ssh()
    sftp = c.open_sftp()

    print("=== Step 1: upload changed files ===")
    for local_rel, remote_rel in FILES:
        local_abs = os.path.abspath(local_rel)
        remote_abs = f"{REMOTE_ROOT}/{remote_rel}"
        if not os.path.exists(local_abs):
            print(f"!! 缺失本地文件: {local_abs}")
            sys.exit(2)
        upload(sftp, local_abs, remote_abs)

    print("\n=== Step 2: rebuild h5-web container ===")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -40",
        timeout=2400,
    )
    if rc != 0:
        print("!! docker compose build h5-web 失败")
        sys.exit(3)

    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose up -d h5-web 2>&1 | tail -20",
        timeout=600,
    )
    if rc != 0:
        print("!! docker compose up h5-web 失败")
        sys.exit(4)

    print("\n=== Step 3: wait & container status ===")
    time.sleep(20)
    run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 4: copy & run new pytest in backend container ===")
    backend_container = f"{DEPLOY_ID}-backend"
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_h5_pay_success_bugfix.py "
          f"{backend_container}:/app/tests/test_h5_pay_success_bugfix.py")
    # 同时把既有的 H5 支付链路测试也跑一遍，确保零回退
    run(c, f"docker cp {REMOTE_ROOT}/backend/tests/test_h5_pay_link_bugfix.py "
          f"{backend_container}:/app/tests/test_h5_pay_link_bugfix.py 2>/dev/null || true")

    rc, out, _ = run(
        c,
        f"docker exec -e PYTHONPATH=/app {backend_container} "
        f"python -m pytest tests/test_h5_pay_success_bugfix.py "
        f"tests/test_h5_pay_link_bugfix.py "
        f"-v --tb=short 2>&1 | tail -120",
        timeout=900,
    )

    print("\n=== Step 5: verify external URLs ===")
    base = "https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID
    for path in [
        "/",
        "/api/health",
        "/checkout",
        "/pay/success",
        "/pay/success?orderId=999999",
        "/sandbox-pay/?order_no=demo&channel=alipay_h5",
    ]:
        run(c, f"curl -s -o /dev/null -w 'GET {path} -> %{{http_code}}\\n' '{base}{path}'")

    sftp.close()
    c.close()
    print("\n=== Deploy & test done ===")


if __name__ == "__main__":
    main()
