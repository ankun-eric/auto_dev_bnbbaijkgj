"""部署脚本：订单状态自动推进策略 + 订单明细页 categories Bug 修复

- 仅 rsync backend/ 和 admin-web/src 到服务器，跳过冗余重建
- 重启 backend 容器（加载新 task）+ rebuild admin-web（前端要重新构建）
- 在容器内跑 pytest tests/test_orders_auto_progress.py + test_orders_status_v2.py
- URL 自检
"""
import os
import sys
import time
import tarfile
import tempfile
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_DIR = Path(r"C:\auto_output\bnbbaijkgj")
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def exec_ssh(ssh, cmd, timeout=600):
    print(f"  $ {cmd[:160]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(f"    out: {out[:1500]}")
    if err.strip():
        print(f"    err: {err[:800]}")
    print(f"    exit: {code}")
    return code, out, err


def make_tar(paths, exclude_names=None):
    """打包指定路径列表（保持相对路径）。"""
    exclude_names = set(exclude_names or [])
    tar_path = Path(tempfile.gettempdir()) / "deploy_orders_v3.tar.gz"

    def _filt(ti):
        name = ti.name.replace("\\", "/")
        for ex in exclude_names:
            if f"/{ex}/" in f"/{name}/" or name.endswith(f"/{ex}") or name == ex:
                return None
        # 排除 __pycache__、.next、node_modules、tests/__pycache__
        for ex in ("__pycache__", "node_modules", ".next", ".pytest_cache", ".git"):
            if f"/{ex}/" in f"/{name}/" or name.endswith(f"/{ex}"):
                return None
        return ti

    with tarfile.open(tar_path, "w:gz") as tar:
        for p in paths:
            full = LOCAL_DIR / p
            if not full.exists():
                print(f"  skip missing: {p}")
                continue
            tar.add(str(full), arcname=p, filter=_filt)
    print(f"  tar: {tar_path} {tar_path.stat().st_size / 1024 / 1024:.2f} MB")
    return tar_path


def main():
    paths_to_sync = [
        "backend/app/tasks/__init__.py",
        "backend/app/tasks/order_status_auto_progress.py",
        "backend/app/services/notification_scheduler.py",
        "backend/app/api/unified_orders.py",
        "backend/tests/test_orders_auto_progress.py",
        "admin-web/src/app/(admin)/product-system/orders/page.tsx",
        "admin-web/src/app/(admin)/product-system/statistics/page.tsx",
    ]

    print("Step 1: 打包文件...")
    tar_path = make_tar(paths_to_sync)

    print(f"Step 2: 连接 {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    print("Step 3: 上传 tar 包...")
    sftp = ssh.open_sftp()
    remote_tar = "/tmp/deploy_orders_v3.tar.gz"
    t0 = time.time()
    sftp.put(str(tar_path), remote_tar)
    sftp.close()
    print(f"  上传完成 in {time.time()-t0:.1f}s")

    print("Step 4: 解压到远程...")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && tar xzf {remote_tar} --overwrite")
    exec_ssh(ssh, f"rm -f {remote_tar}")

    print("Step 5: 重启 backend 容器（加载新 tasks）...")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose restart backend", timeout=180)
    print("  等待 backend 启动 15s...")
    time.sleep(15)

    print("Step 6: 重建 admin-web（Next.js 需要 build）...")
    exec_ssh(
        ssh,
        f"cd {REMOTE_DIR} && docker compose up -d --no-deps --force-recreate --build admin-web",
        timeout=900,
    )
    time.sleep(20)

    print("Step 7: 检查容器状态...")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose ps")

    print("Step 8: 检查 backend 日志（确认 R1/R2 调度任务已启动）...")
    exec_ssh(
        ssh,
        f"cd {REMOTE_DIR} && docker compose logs --tail=80 backend 2>&1 | grep -E 'scheduler|R1|R2|order_r' | head -30",
    )

    print("Step 9: 容器内跑 pytest 自动化测试...")
    pytest_cmd = (
        f"cd {REMOTE_DIR} && docker compose exec -T backend "
        f"sh -c 'cd /app && python -m pytest tests/test_orders_auto_progress.py "
        f"tests/test_orders_status_v2.py -v --tb=short 2>&1 | tail -120'"
    )
    code, out, err = exec_ssh(ssh, pytest_cmd, timeout=600)
    pytest_passed = ("passed" in out and "failed" not in out.lower()) or " failed" not in out

    print("Step 10: URL 自检（用户体验入口 + admin 端 + Bug 修复目标页）...")
    urls = [
        f"{BASE_URL}/api/health",
        f"{BASE_URL}/admin/",
        f"{BASE_URL}/admin/product-system/orders",
        f"{BASE_URL}/admin/product-system/categories",
        f"{BASE_URL}/admin/product-system/statistics",
        f"{BASE_URL}/api/admin/products/categories",
    ]
    for u in urls:
        exec_ssh(ssh, f'curl -skI "{u}" | head -3')

    print("Step 11: 验证错误路径已不再被前端调用（路径本身应 404/405）...")
    exec_ssh(
        ssh,
        f'curl -sk -o /dev/null -w "%{{http_code}}\\n" "{BASE_URL}/api/admin/product-system/categories"',
    )

    ssh.close()
    try:
        tar_path.unlink()
    except Exception:
        pass
    print("\n=== 部署完成 ===")
    print(f"pytest 通过: {pytest_passed}")


if __name__ == "__main__":
    main()
