"""[PRD 订单状态机简化方案 v1.0] 增量部署。

只更新后端 + admin-web + h5-web 中改动的文件（小程序/Flutter 走打包通道）。
- 后端：复制改动的 .py 文件到容器，docker compose restart backend
- admin-web：复制改动的 .tsx 到宿主，docker compose up -d --build admin-web
- h5-web：复制改动的 .tsx 到宿主，docker compose up -d --build h5
"""
import io
import os
import sys
import time
import tarfile
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = r"C:\auto_output\bnbbaijkgj"

# 本次需要同步的相对路径列表（只更新这些）
FILES_TO_SYNC = [
    # 后端
    "backend/app/api/unified_orders.py",
    "backend/app/api/product_admin.py",
    "backend/app/tasks/order_status_auto_progress.py",
    "backend/app/services/notification_scheduler.py",
    "backend/app/services/schema_sync.py",
    "backend/tests/test_orders_status_simplification.py",
    "backend/tests/test_orders_auto_progress.py",
    "backend/tests/test_orders_status_v2.py",
    "backend/tests/test_book_after_pay_bugfix.py",
    # H5
    "h5-web/src/app/unified-order/[id]/page.tsx",
    "h5-web/src/app/unified-orders/page.tsx",
    # Admin
    "admin-web/src/app/(admin)/product-system/orders/page.tsx",
]


def exec_ssh(ssh, cmd, timeout=600, log=True):
    if log:
        print(f"  $ {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if log:
        if out.strip():
            print(f"    stdout: {out[-500:]}")
        if err.strip():
            print(f"    stderr: {err[-500:]}")
        print(f"    exit: {exit_code}")
    return exit_code, out, err


def main():
    print("=== 阶段 1：打包待同步文件 ===")
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
        for rel in FILES_TO_SYNC:
            full = os.path.join(LOCAL_DIR, rel)
            if not os.path.exists(full):
                print(f"  ⚠️ 跳过不存在: {rel}")
                continue
            tar.add(full, arcname=rel)
            print(f"  + {rel}")
    tar_buf.seek(0)
    tar_data = tar_buf.read()
    print(f"  压缩包大小: {len(tar_data) / 1024:.1f} KB")

    print("\n=== 阶段 2：连接服务器 ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    print("\n=== 阶段 3：上传增量包 ===")
    sftp = ssh.open_sftp()
    remote_tar = "/tmp/deploy_status_simp.tar.gz"
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_data)
    sftp.close()
    print(f"  ✓ 上传完成 → {remote_tar}")

    print("\n=== 阶段 4：在服务器上解压（覆盖到 REMOTE_DIR） ===")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && tar xzf {remote_tar} --overwrite")
    exec_ssh(ssh, f"rm -f {remote_tar}")

    print("\n=== 阶段 5：把改动的 .py 文件 cp 到 backend 容器内 ===")
    backend_files = [f for f in FILES_TO_SYNC if f.startswith("backend/")]
    for rel in backend_files:
        # rel 形如 backend/app/api/unified_orders.py → 容器内是 /app/app/api/unified_orders.py
        in_container = rel.replace("backend/", "/app/", 1)
        cmd = (
            f"docker cp {REMOTE_DIR}/{rel} "
            f"6b099ed3-7175-4a78-91f4-44570c84ed27-backend:{in_container}"
        )
        exec_ssh(ssh, cmd)

    print("\n=== 阶段 6：重启 backend 容器（拉起新代码 + 重新执行 schema_sync 迁移） ===")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose restart backend", timeout=180)

    print("\n=== 阶段 7：admin-web / h5-web rebuild（只 build 改动的两个） ===")
    exec_ssh(
        ssh,
        f"cd {REMOTE_DIR} && docker compose up -d --build --force-recreate admin-web h5",
        timeout=600,
    )

    print("\n=== 阶段 8：等待容器就绪 (45s) ===")
    time.sleep(45)

    print("\n=== 阶段 9：状态检查 ===")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose ps")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose logs --tail=20 backend")

    print("\n=== 阶段 10：URL 自检 ===")
    urls = [
        "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/",
        "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/",
        "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs",
    ]
    for url in urls:
        exec_ssh(ssh, f'curl -skI "{url}" | head -3')

    ssh.close()
    print("\n=== DEPLOYMENT COMPLETE ===")


if __name__ == "__main__":
    main()
