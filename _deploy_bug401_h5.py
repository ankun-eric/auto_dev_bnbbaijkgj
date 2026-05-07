"""[BUGFIX-UO-20260507-001] H5 容器 rebuild 脚本"""
from __future__ import annotations
import subprocess, time

SSH_HOST = "ubuntu@newbb.test.bangbangvip.com"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PREFIX = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def ssh(cmd: str, timeout=900):
    full = ["ssh", "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd]
    print("[CMD]", cmd[:200])
    r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    if r.stdout: print(r.stdout[-3000:])
    if r.stderr and r.returncode != 0: print("[ERR]", r.stderr[-2000:])
    print("[RC]", r.returncode)
    return r


def main():
    # 1. 先用 backend 容器内 pytest 跑一下相关测试
    print("=== Step 1: backend 容器内执行新增单元测试 ===")
    ssh(
        f"docker exec {PREFIX}-backend python -m pytest "
        "tests/test_bugfix_uo_20260507_001.py "
        "tests/test_payment_method_text_priority_v10.py "
        "-v --tb=short 2>&1 | tail -60"
    )

    # 2. backend 健康检查（直接访问容器内端点）
    print("=== Step 2: backend health（容器内 8000 端口）===")
    ssh(f"docker exec {PREFIX}-backend curl -fsS http://127.0.0.1:8000/api/health || true")

    # 3. rebuild h5-web
    print("=== Step 3: rebuild h5-web ===")
    ssh(f"cd {PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -50", timeout=1500)

    print("=== Step 4: up -d h5-web ===")
    ssh(f"cd {PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -20")

    print("=== Step 5: 等待 h5 健康 ===")
    for i in range(25):
        time.sleep(4)
        r = ssh(
            "curl -fsS -o /dev/null -w '%{http_code}\\n' "
            f"https://newbb.test.bangbangvip.com/autodev/{PREFIX}/merchant/orders || true"
        )
        if "200" in (r.stdout or "") or "302" in (r.stdout or "") or "307" in (r.stdout or ""):
            print(f"[OK] h5 ready at attempt {i+1}")
            break

    print("=== Done ===")


if __name__ == "__main__":
    main()
