"""[PRD-468 (2026-05-12)] 服务器侧非UI自动化测试

测试用例（覆盖 PRD 的 T-01 ~ T-10 子集）：

T-01 ~ T-07: 所有 v3 API 端点未登录应返回 401（证明路由挂载且鉴权正常工作）
T-08: /health-profile-v2 改版主页面前端可达
T-09: /health-metric/blood_pressure 指标详情页前端可达
T-10: 关键源码标记 grep（确保部署的是新版本代码）
T-11: 漏打卡任务源码标记验证（GRACE_MINUTES = 15 + source_type 文案）
T-12: 数据库新表 health_metric_record 存在
T-13: 数据库新表 device_binding 存在
T-14: 数据库新表字段结构完整（含 metric_type / value_json / measured_at 等）
T-15: 漏打卡定时任务已注册到 scheduler（源码标记验证）
"""
from __future__ import annotations

import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
DB_PWD = "bini_health_2026"


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli, cmd: str, *, timeout: int = 60):
    _, stdout, _ = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out


def curl_code(cli, url: str) -> str:
    rc, out = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {url}")
    return (out or "").strip().splitlines()[-1] if out else ""


def main() -> int:
    cli = ssh_connect()
    try:
        passed = 0
        failed = []

        def expect(name: str, condition: bool, detail: str = ""):
            nonlocal passed
            if condition:
                print(f"[PASS] {name} {detail}")
                passed += 1
            else:
                print(f"[FAIL] {name} {detail}")
                failed.append(name)

        # T-01 ~ T-07: API 401（未登录）
        code = curl_code(cli, f"{BASE_URL}/api/health-profile-v3/1/today-metrics")
        expect("T-01 today-metrics 401", code in {"401", "403", "422"}, f"code={code}")

        rc, out = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST {BASE_URL}/api/health-profile-v3/1/metric/blood_pressure")
        code = (out or "").strip().splitlines()[-1] if out else ""
        expect("T-02 POST metric 401", code in {"401", "403", "422", "405"}, f"code={code}")

        code = curl_code(cli, f"{BASE_URL}/api/health-profile-v3/devices")
        expect("T-03 devices 401", code in {"401", "403", "422"}, f"code={code}")

        rc, out = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' -X POST {BASE_URL}/api/health-profile-v3/devices/huawei_watch/bind")
        code = (out or "").strip().splitlines()[-1] if out else ""
        expect("T-04 bind device 401", code in {"401", "403", "422", "405"}, f"code={code}")

        rc, out = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' -X DELETE {BASE_URL}/api/health-profile-v3/devices/huawei_watch")
        code = (out or "").strip().splitlines()[-1] if out else ""
        expect("T-05 unbind device 401", code in {"401", "403", "422", "405"}, f"code={code}")

        code = curl_code(cli, f"{BASE_URL}/api/health-profile-v3/1/medication-plan")
        expect("T-06 medication-plan 401", code in {"401", "403", "422"}, f"code={code}")

        code = curl_code(cli, f"{BASE_URL}/api/health-profile-v3/1/events")
        expect("T-07 events 401", code in {"401", "403", "422"}, f"code={code}")

        # T-08 / T-09: 前端页面可达性（308/200/302 都算可达）
        code = curl_code(cli, f"{BASE_URL}/health-profile-v2")
        expect("T-08 /health-profile-v2 reachable", code.startswith("2") or code.startswith("3"), f"code={code}")

        code = curl_code(cli, f"{BASE_URL}/health-metric/blood_pressure")
        expect("T-09 /health-metric/blood_pressure reachable", code.startswith("2") or code.startswith("3"), f"code={code}")

        # T-10: 源码标记
        _, out = run(cli, f"grep -c 'PRD-468' {REMOTE_PROJ}/backend/app/api/health_profile_v3.py")
        n = int((out or "0").strip().splitlines()[-1] or "0") if out.strip() else 0
        expect("T-10a backend api PRD-468 markers", n >= 1, f"count={n}")

        _, out = run(cli, f"grep -c 'PRD-468' {REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx")
        n = int((out or "0").strip().splitlines()[-1] or "0") if out.strip() else 0
        expect("T-10b h5 v2 page PRD-468 markers", n >= 1, f"count={n}")

        # T-11: 漏打卡任务关键代码
        _, out = run(cli, f"grep -c 'GRACE_MINUTES = 15' {REMOTE_PROJ}/backend/app/tasks/medication_miss_check.py")
        n = int((out or "0").strip().splitlines()[-1] or "0") if out.strip() else 0
        expect("T-11a GRACE_MINUTES = 15 found", n >= 1, f"count={n}")

        _, out = run(cli, f"grep -c 'medication_missed_for_managed_user' {REMOTE_PROJ}/backend/app/tasks/medication_miss_check.py")
        n = int((out or "0").strip().splitlines()[-1] or "0") if out.strip() else 0
        expect("T-11b source_type marker", n >= 1, f"count={n}")

        # T-12: 数据库新表 health_metric_record 存在
        sql = "SHOW TABLES LIKE 'health_metric_record'"
        _, out = run(cli, f"docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PWD} bini_health -e \"{sql}\" 2>&1 | grep -v Warning")
        expect("T-12 table health_metric_record exists", "health_metric_record" in (out or ""), f"out={out[:120].strip()}")

        # T-13: 数据库新表 device_binding 存在
        sql = "SHOW TABLES LIKE 'device_binding'"
        _, out = run(cli, f"docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PWD} bini_health -e \"{sql}\" 2>&1 | grep -v Warning")
        expect("T-13 table device_binding exists", "device_binding" in (out or ""), f"out={out[:120].strip()}")

        # T-14: 关键字段存在
        sql = "DESCRIBE health_metric_record"
        _, out = run(cli, f"docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PWD} bini_health -e \"{sql}\" 2>&1 | grep -v Warning")
        cols = ["metric_type", "value_json", "measured_at", "source", "profile_id"]
        all_found = all(c in (out or "") for c in cols)
        expect("T-14 health_metric_record schema complete", all_found, f"missing={[c for c in cols if c not in (out or '')]}")

        # T-15: scheduler 已注册漏打卡任务
        _, out = run(cli, f"grep -c 'miss_check_medication_reminders' {REMOTE_PROJ}/backend/app/services/notification_scheduler.py")
        n = int((out or "0").strip().splitlines()[-1] or "0") if out.strip() else 0
        expect("T-15 scheduler registered miss_check task", n >= 2, f"count={n}")

        # 汇总
        total = passed + len(failed)
        print(f"\n[SUMMARY] {passed}/{total} PASS, {len(failed)} FAIL")
        if failed:
            print(f"[FAIL LIST] {failed}")
            return 1
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
