"""
[PRD-AIHOME-CARE-V1] 部署脚本（rebuild backend + h5）
"""
import subprocess
import sys
import time
import os

HOST = "ubuntu@newbb.test.bangbangvip.com"
REMOTE_ROOT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_NAME = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_NAME}"


def run(cmd, check=True, timeout=600):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "")[-2000:]
    err = (r.stderr or "")[-2000:]
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    if check and r.returncode != 0:
        sys.exit(f"FAILED rc={r.returncode}")
    return r


def scp_file(local, remote):
    run(f'scp -o StrictHostKeyChecking=no "{local}" {HOST}:{remote}')


def scp_dir(local, remote_dir):
    # 先确保目录存在
    parent = "/".join(remote_dir.rstrip("/").split("/")[:-1])
    run(f'ssh -o StrictHostKeyChecking=no {HOST} "mkdir -p {parent}"')
    run(f'scp -o StrictHostKeyChecking=no -r "{local}" {HOST}:{remote_dir}')


def ssh(cmd, check=True, timeout=600):
    return run(f'ssh -o StrictHostKeyChecking=no {HOST} "{cmd}"', check=check, timeout=timeout)


def main():
    # 1. 上传 backend 文件
    print("== 1. 同步 backend 代码 ==")
    backend_files = [
        ("backend/app/api/ai_home_care_v1.py", f"{REMOTE_ROOT}/backend/app/api/ai_home_care_v1.py"),
        ("backend/app/main.py", f"{REMOTE_ROOT}/backend/app/main.py"),
        ("backend/tests/test_ai_home_care_v1.py", f"{REMOTE_ROOT}/backend/tests/test_ai_home_care_v1.py"),
    ]
    for local, remote in backend_files:
        scp_file(local, remote)

    # 2. 重建 backend（rebuild + restart）
    print("== 2. 重建 backend ==")
    ssh(
        f"cd {REMOTE_ROOT} && docker compose build backend && docker compose up -d backend",
        timeout=900,
    )

    # 等待 backend 就绪（max 60s）
    print("== 等待 backend 就绪 ==")
    for i in range(30):
        time.sleep(3)
        r = ssh(
            f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/care-v1/sos/keywords",
            check=False,
        )
        if "200" in (r.stdout or ""):
            print(f"✓ backend 就绪 (轮次 {i})")
            break
    else:
        print("✗ backend 未就绪，继续部署 h5")

    # 3. 同步 h5-web 关怀模式新页面
    print("== 3. 同步 h5-web 关怀模式页面 ==")
    ssh(f"mkdir -p {REMOTE_ROOT}/h5-web/src/app/welcome-mode {REMOTE_ROOT}/h5-web/src/app/care-home")
    scp_file("h5-web/src/app/welcome-mode/page.tsx", f"{REMOTE_ROOT}/h5-web/src/app/welcome-mode/page.tsx")
    scp_file("h5-web/src/app/care-home/page.tsx", f"{REMOTE_ROOT}/h5-web/src/app/care-home/page.tsx")

    # 4. 重建 h5 容器
    print("== 4. 重建 h5-web ==")
    ssh(
        f"cd {REMOTE_ROOT} && docker compose build h5 && docker compose up -d h5",
        timeout=900,
    )

    # 等 h5 就绪
    print("== 等待 h5 就绪 ==")
    for i in range(30):
        time.sleep(3)
        r = ssh(
            f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/welcome-mode",
            check=False,
        )
        code = (r.stdout or "").strip()
        if code in ("200", "307", "301", "302"):
            print(f"✓ h5 就绪 (code={code})")
            break

    # 5. 简单冒烟测试
    print("== 5. 冒烟测试 ==")
    r = ssh(
        f"curl -s {BASE_URL}/api/care-v1/sos/keywords | head -c 300",
        check=False,
    )
    print("关键词 API 返回:", r.stdout)

    r2 = ssh(
        f'''curl -s -X POST {BASE_URL}/api/care-v1/sos/detect -H 'Content-Type: application/json' -d '{{\\"text\\":\\"救命\\"}}' | head -c 300''',
        check=False,
    )
    print("SOS 检测 API 返回:", r2.stdout)

    print("\n=== 部署完成 ===")


if __name__ == "__main__":
    main()
