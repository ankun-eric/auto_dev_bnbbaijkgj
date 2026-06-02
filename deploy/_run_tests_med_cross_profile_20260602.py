"""[BUGFIX-MED-CROSS-PROFILE 2026-06-02] 在后端容器内运行专项测试 + 看板回归测试。"""
import _sshlib as ssh

C = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"


def run(title, inner_cmd, timeout=600):
    print(f"\n===== {title} =====")
    cmd = f"docker exec {C} sh -lc {ssh_quote(inner_cmd)}"
    code, out, err = ssh.run(cmd, timeout=timeout)
    print("EXIT", code)
    if out:
        print(out[-8000:])
    if err:
        print("--- STDERR ---")
        print(err[-3000:])
    return code, out, err


def ssh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


# 0. 依赖检查 / 必要时安装
run("Check & install test deps", (
    "cd /app && python -c 'import pytest' 2>/dev/null || "
    "pip install -q pytest pytest-asyncio aiosqlite >/dev/null 2>&1; "
    "python -c 'import pytest,pytest_asyncio,aiosqlite,sys; print(\"pytest\", pytest.__version__)'"
), timeout=300)

# 1. 本 Bug 专项测试
run("Run cross-profile fix tests", (
    "cd /app && python -m pytest tests/test_med_dashboard_cross_profile_fix_20260602.py -v -p no:cacheprovider 2>&1 | tail -40"
), timeout=600)

# 2. 看板原有测试回归
run("Regression: health_dashboard", (
    "cd /app && python -m pytest tests/test_health_dashboard.py -v -p no:cacheprovider 2>&1 | tail -40"
), timeout=600)

print("\nDONE")
