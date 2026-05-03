#!/usr/bin/env python3
"""[修改预约 Bug 修复 v1.0] 增量部署脚本

策略：
1. SFTP 上传本次改动的后端、H5 源文件到服务器对应路径
2. 在服务器上 docker compose build + up backend + h5-web（仅这两个服务需要 rebuild）
3. 等待容器健康
4. 验证基础访问
"""
import paramiko
import sys
import os
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"

# 本次改动的文件清单：local_path -> remote_path（相对 REMOTE_ROOT）
FILES = [
    # 后端
    ("backend/app/api/unified_orders.py", "backend/app/api/unified_orders.py"),
    ("backend/app/schemas/unified_orders.py", "backend/app/schemas/unified_orders.py"),
    ("backend/tests/test_modify_appointment_bugfix.py", "backend/tests/test_modify_appointment_bugfix.py"),
    # H5
    ("h5-web/src/app/unified-order/[id]/page.tsx", "h5-web/src/app/unified-order/[id]/page.tsx"),
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
        print(out[-3000:])
    if err:
        print("STDERR:", err[-1500:])
    print(f"--- EXIT {rc} ---")
    return rc, out, err


def upload(sftp, local, remote):
    # 确保远程目录存在
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

    print("\n=== Step 2: rebuild backend & h5-web containers ===")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose build backend h5-web 2>&1 | tail -30",
        timeout=1800,
    )
    if rc != 0:
        print("!! docker compose build 失败")
        sys.exit(3)

    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose up -d backend h5-web 2>&1 | tail -20",
        timeout=600,
    )
    if rc != 0:
        print("!! docker compose up 失败")
        sys.exit(4)

    print("\n=== Step 3: wait & check health ===")
    time.sleep(10)
    run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    # 简单健康验证
    run(
        c,
        f"docker exec {DEPLOY_ID}-backend curl -s -o /dev/null -w 'backend_health=%{{http_code}}\\n' http://127.0.0.1:8000/api/health || echo 'backend health request failed'",
    )

    sftp.close()
    c.close()
    print("\n=== Deploy done ===")


if __name__ == "__main__":
    main()
