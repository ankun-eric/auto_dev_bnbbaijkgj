"""远程跑 Bug 367 修复后回归测试。"""
import paramiko, sys, time

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BC = f"{DEPLOY_ID}-backend"


def run(cmd, timeout=900):
    print(f"\n>>> {cmd}")
    sys.stdout.flush()
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[stderr]\n{err}")
    print(f"[exit={code}]")
    sys.stdout.flush()
    return code, out, err


try:
    # 0. 验证代码已部署
    run(f"docker exec {BC} grep -c 'CUSTOMER_CLIENTS' /app/app/utils/client_source.py")
    run(f"docker exec {BC} grep -c 'require_customer_client_session' /app/app/api/unified_orders.py")

    # 1. 跑修复专项测试
    run(
        f"docker exec {BC} python -m pytest tests/test_bugfix_customer_client_session_v1.py -v --tb=short 2>&1 | tail -120",
        timeout=600,
    )

    # 2. 跑订单相关回归
    targets = [
        "tests/test_bugfix_customer_client_session_v1.py",
        "tests/test_prd05_verify_lockdown_v1.py",
        "tests/test_prd03_reschedule_v1.py",
        "tests/test_modify_appointment_bugfix.py",
        "tests/test_orders_status_v2.py",
        "tests/test_orders_aftersales_v3.py",
        "tests/test_h5_pay_link_bugfix.py",
        "tests/test_h5_pay_success_bugfix.py",
        "tests/test_on_site_fulfillment_v1.py",
    ]
    cmd = f"docker exec {BC} python -m pytest {' '.join(targets)} --tb=short 2>&1 | tail -40"
    run(cmd, timeout=900)

    # 3. 全量 collect 健康检查
    run(
        f"docker exec {BC} python -m pytest --collect-only -q 2>&1 | tail -10",
        timeout=300,
    )

    # 4. 实际 HTTP smoke：调一个 customer 接口断言新错误文案
    run(
        "curl -s -X POST 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/orders/unified/999999/appointment' "
        "-H 'Content-Type: application/json' -H 'Authorization: Bearer fake' -H 'Client-Type: pc-web' -d '{}'"
    )
    run(
        "curl -s -X POST 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/orders/unified/999999/appointment' "
        "-H 'Content-Type: application/json' -H 'Authorization: Bearer fake' -H 'Client-Type: h5-user' -d '{}'"
    )

finally:
    cli.close()
