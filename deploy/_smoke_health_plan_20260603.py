"""[PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-03] 烟雾测试：验证健康计划页面可达"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sshlib import DEPLOY_ID, run

BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

PATHS = [
    "/health-plan",
    "/health-plan/edit",
    "/health-plan/result",
    "/health-plan/checkin",
    "/api/health",
]


def main():
    cmd_parts = []
    for p in PATHS:
        cmd_parts.append(
            f"echo {p} $(curl -skL -o /dev/null -w '%{{http_code}}' {BASE}{p})"
        )
    cmd = " ; ".join(cmd_parts)
    code, out, err = run(cmd, timeout=120)
    print(out)
    if err:
        print("STDERR:", err)


if __name__ == "__main__":
    main()
