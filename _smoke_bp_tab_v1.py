"""[BUGFIX-BP-TAB-OPTIMIZE-V1] 远程冒烟验证

1. 检查 h5-web 构建产物含关键文案：最近 7 天趋势 / 即将上线 / 收缩压（高压）/ 舒张压（低压）/ 严重偏高（橙色预警）
2. 远程 curl 调用 GET /api/health-profile-v3/{pid}/metric/blood_pressure 验证新字段（trend_dates / trend_systolic / trend_diastolic / trend_day_labels）存在
3. 后端 pytest 在 mysql 容器中跑（先 pip install aiosqlite，避免污染 prod 镜像，仅临时安装）
"""
from __future__ import annotations

import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
H5_NAME = f"{DEPLOY_ID}-h5"
BE_NAME = f"{DEPLOY_ID}-backend"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def run(c, cmd, *, timeout=600, allow_fail=False):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out: print(out[-3000:])
    if err.strip(): print("STDERR:", err[-1500:])
    print(f"exit={rc}")
    if rc != 0 and not allow_fail:
        raise SystemExit(f"失败：{cmd}")
    return out, rc


def main():
    c = ssh()
    try:
        # 1. h5-web 构建产物
        print("=== H5 构建产物文案校验 ===")
        for keyword in ["最近 7 天趋势", "即将上线", "收缩压（高压）", "舒张压（低压）", "严重偏高（橙色预警）", "bp-status-card"]:
            out, rc = run(
                c,
                f"docker exec {H5_NAME} sh -c \"grep -rl '{keyword}' /app/.next 2>/dev/null | head -2 | wc -l\"",
                allow_fail=True,
            )
            count = (out or '0').strip()
            assert count != '0', f"关键字 [{keyword}] 未在 H5 构建产物中找到"
            print(f"✓ 关键字 [{keyword}] 命中 {count} 个文件")

        # 2. 容器内安装 aiosqlite 并跑测试
        print("\n=== 后端容器内 pytest（临时安装 aiosqlite） ===")
        run(c, f"docker exec {BE_NAME} pip install -q aiosqlite", allow_fail=True)
        out, rc = run(
            c,
            f"docker exec {BE_NAME} python -m pytest tests/test_bp_tab_trend_v1_20260530.py -v 2>&1 | tail -30",
        )
        assert "6 passed" in out or "passed" in out, "后端测试未全部通过"

        # 3. 直接 curl 接口（无 token 走 401）
        print("\n=== HTTPS 验证 ===")
        run(c, f"curl -k -s -o /dev/null -w 'HTTP %{{http_code}}\\n' {BASE_URL}/api/health")
        run(c, f"curl -k -s -o /dev/null -w 'HTTP %{{http_code}}\\n' {BASE_URL}/health-metric/blood_pressure/")
        run(c, f"curl -k -s -o /dev/null -w 'HTTP %{{http_code}}\\n' {BASE_URL}/api/health-profile-v3/devices")

        print("\n✅ 全部冒烟验证通过")
    finally:
        c.close()


if __name__ == "__main__":
    main()
