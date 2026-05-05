"""安装 pytest+pytest-asyncio 后在容器内执行新增的改期通知测试。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONT = f"{DEPLOY_ID}-backend"


def run(ssh, cmd, timeout=300):
    print(f"\n[REMOTE] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err)
    return code, out


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

    print("=== 安装 pytest / pytest-asyncio / aiosqlite ===")
    run(ssh, f"docker exec {CONT} pip install --no-cache-dir pytest pytest-asyncio aiosqlite httpx -i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com --quiet 2>&1 | tail -5")

    print("\n=== 运行 test_reschedule_notification_v1.py ===")
    code, out = run(
        ssh,
        f"docker exec -e WECHAT_MINI_APP_ID= -e WECHAT_MINI_APP_SECRET= -e RESCHEDULE_SMS_TEMPLATE_ID= -e APP_PUSH_PROVIDER= {CONT} "
        f"python -m pytest tests/test_reschedule_notification_v1.py -v --tb=short --asyncio-mode=auto 2>&1",
        timeout=180,
    )

    ssh.close()
    if "passed" in out and "failed" not in out.split("=========")[-1]:
        print("\n[PASS] all tests passed")
        return 0
    print("\n[FAIL] tests failed")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
