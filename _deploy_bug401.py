"""[BUGFIX-UO-20260507-001] 部署脚本：商家端订单预约时间&支付方式修复

部署内容：
- backend: merchant.py、merchant_v1.py、unified_orders.py、alipay_notify.py、schemas/merchant_v1.py、tests/test_bugfix_uo_20260507_001.py
- h5-web: merchant/orders/page.tsx、merchant/m/orders/[id]/page.tsx
"""
from __future__ import annotations

import subprocess
import sys
import time

SSH_HOST = "ubuntu@newbb.test.bangbangvip.com"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_PREFIX = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"[CMD] {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=900, **kwargs)
    if res.stdout:
        print(res.stdout[:6000])
    if res.stderr and res.returncode != 0:
        print("[STDERR]", res.stderr[:3000])
    print(f"[RC] {res.returncode}")
    return res


def scp(local: str, remote: str) -> None:
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", local, f"{SSH_HOST}:{remote}"]
    res = run(cmd)
    if res.returncode != 0:
        raise SystemExit(f"scp failed: {local} -> {remote}")


def ssh(remote_cmd: str) -> subprocess.CompletedProcess:
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", SSH_HOST, remote_cmd]
    return run(cmd)


def main() -> None:
    print("=== Step 1: 上传后端 + 测试文件 ===")
    backend_files = [
        ("backend/app/api/merchant.py", f"{PROJECT_DIR}/backend/app/api/merchant.py"),
        ("backend/app/api/merchant_v1.py", f"{PROJECT_DIR}/backend/app/api/merchant_v1.py"),
        ("backend/app/api/unified_orders.py", f"{PROJECT_DIR}/backend/app/api/unified_orders.py"),
        ("backend/app/api/alipay_notify.py", f"{PROJECT_DIR}/backend/app/api/alipay_notify.py"),
        ("backend/app/schemas/merchant_v1.py", f"{PROJECT_DIR}/backend/app/schemas/merchant_v1.py"),
        ("backend/tests/test_bugfix_uo_20260507_001.py", f"{PROJECT_DIR}/backend/tests/test_bugfix_uo_20260507_001.py"),
    ]
    for local, remote in backend_files:
        scp(local, remote)

    print("\n=== Step 2: 上传 h5-web 商家订单页面源码 ===")
    h5_files = [
        ("h5-web/src/app/merchant/orders/page.tsx", f"{PROJECT_DIR}/h5-web/src/app/merchant/orders/page.tsx"),
        ("h5-web/src/app/merchant/m/orders/[id]/page.tsx", f"{PROJECT_DIR}/h5-web/src/app/merchant/m/orders/[id]/page.tsx"),
    ]
    for local, remote in h5_files:
        scp(local, remote)

    print("\n=== Step 3: 同步后端代码到 backend 容器 (/app) ===")
    # backend 镜像里 app 代码挂载方式：从 docker-compose 看是 build 而不是 volume，
    # 需要 docker cp 把改动文件拷进容器再 reload。
    backend_container = f"{PROJECT_PREFIX}-backend"
    for local_path, _ in backend_files:
        # 容器内路径是 /app/<local 去掉 backend/ 前缀>
        in_container = "/app/" + local_path.split("/", 1)[1]
        ssh(f"docker cp {PROJECT_DIR}/{local_path} {backend_container}:{in_container}")

    print("\n=== Step 4: 重启 backend 容器以让代码生效 ===")
    ssh(f"docker restart {backend_container}")

    print("\n=== Step 5: 等待 backend 健康 ===")
    for i in range(15):
        time.sleep(4)
        res = ssh(
            "curl -fsS http://127.0.0.1/autodev/" + PROJECT_PREFIX + "/api/health || true"
        )
        if "ok" in (res.stdout or "").lower() or "healthy" in (res.stdout or "").lower():
            print(f"[OK] backend healthy at attempt {i+1}")
            break
    else:
        print("[WARN] backend health check 未通过，但继续后续步骤")

    print("\n=== Step 6: rebuild h5 容器以让前端代码生效 ===")
    h5_container = f"{PROJECT_PREFIX}-h5"
    # h5-web 在容器中是 next build 后的产物，必须 docker compose build 重建
    rebuild = ssh(
        f"cd {PROJECT_DIR} && docker compose build h5 2>&1 | tail -40"
    )
    if rebuild.returncode != 0:
        print("[WARN] docker compose build h5 失败，尝试用 docker-compose v1 语法")
        rebuild = ssh(
            f"cd {PROJECT_DIR} && docker-compose build h5 2>&1 | tail -40"
        )
    ssh(f"cd {PROJECT_DIR} && (docker compose up -d h5 || docker-compose up -d h5)")

    print("\n=== Step 7: 等待 h5 健康 ===")
    for i in range(20):
        time.sleep(4)
        res = ssh(
            "curl -fsS -o /dev/null -w '%{http_code}' "
            f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_PREFIX}/ || true"
        )
        if "200" in (res.stdout or ""):
            print(f"[OK] h5 healthy at attempt {i+1}")
            break

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
