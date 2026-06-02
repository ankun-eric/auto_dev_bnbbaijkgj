"""[PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-03] 在 backend 容器内运行健康打卡测试。

由于 backend 容器内默认未安装 pytest，先安装相关依赖再运行测试。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sshlib import DEPLOY_ID, run

CONTAINER = f"{DEPLOY_ID}-backend"


def step(title: str, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print(f"\n>>> {title}")
    print(f"$ {cmd}")
    code, out, err = run(cmd, timeout=timeout)
    if out:
        print(out)
    if err:
        print(f"[STDERR] {err}")
    print(f"[exit {code}]")
    return code, out


def main():
    step(
        "1. 安装 pytest 依赖（一次性）",
        f"docker exec {CONTAINER} pip install --no-cache-dir "
        "-i https://mirrors.cloud.tencent.com/pypi/simple "
        "--trusted-host mirrors.cloud.tencent.com "
        "pytest pytest-asyncio aiosqlite httpx",
        timeout=300,
    )

    code, out = step(
        "2. 运行健康打卡测试",
        f"docker exec {CONTAINER} bash -lc "
        f"'cd /app && python -m pytest tests/test_health_plan_checkin_v1_20260602.py "
        f"-v --tb=short --no-header -p no:cacheprovider 2>&1'",
        timeout=600,
    )

    print("\n========================================")
    if "passed" in out and "failed" not in out and code == 0:
        print("[OK] 全部通过")
    else:
        print("[FAIL] 存在失败用例")
    sys.exit(code)


if __name__ == "__main__":
    main()
