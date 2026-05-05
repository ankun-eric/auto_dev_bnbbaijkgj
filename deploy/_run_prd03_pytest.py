"""[PRD-03] 在已部署的新 backend 容器内重跑 pytest（验证 utils.reschedule_validator 可被导入）。"""
from __future__ import annotations

import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
container_be = f"{DEPLOY_ID}-backend"


def run(ssh, cmd, timeout=300):
    print(f"\n[REMOTE] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[:2000])
    return code, out, err


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

    # 关键：把测试文件再 cp 进新容器（容器是新 image，但 image 里的 tests 目录是 build 时打进去的）
    print("\n=== 把 PRD-03 测试文件 cp 进新 backend 容器 ===")
    run(
        ssh,
        f"docker cp {REMOTE_PROJ}/backend/tests/test_prd03_reschedule_v1.py "
        f"{container_be}:/app/tests/test_prd03_reschedule_v1.py",
        timeout=60,
    )

    print("\n=== 容器内验证 reschedule_validator 可导入 ===")
    run(
        ssh,
        f"docker exec {container_be} python -c "
        f"\"from app.utils.reschedule_validator import validate_reschedule_lenient; print('IMPORT OK')\"",
        timeout=30,
    )

    print("\n=== 容器内安装 pytest（新 image 是干净的） ===")
    run(
        ssh,
        f"docker exec {container_be} pip install --quiet --no-cache-dir "
        f"-i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com "
        f"pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -10",
        timeout=180,
    )

    print("\n=== 容器内运行 PRD-03 + PRD-02 + PRD-01 单元测试 ===")
    code, out, _ = run(
        ssh,
        f"docker exec {container_be} python -m pytest "
        f"tests/test_prd03_reschedule_v1.py "
        f"tests/test_prd02_dashboard_v1.py "
        f"tests/test_time_slots_unified_v1.py "
        f"-v --noconftest -p no:cacheprovider --tb=short 2>&1 | tail -200",
        timeout=300,
    )

    last_summary = ""
    for ln in reversed(out.strip().splitlines()):
        if "passed" in ln or "failed" in ln:
            last_summary = ln
            break
    pytest_pass = ("passed" in last_summary) and ("failed" not in last_summary)
    print(f"\n[pytest summary] {last_summary}")
    print(f"  result: {'PASS' if pytest_pass else 'FAIL'}")

    ssh.close()
    return 0 if pytest_pass else 1


if __name__ == "__main__":
    sys.exit(main())
