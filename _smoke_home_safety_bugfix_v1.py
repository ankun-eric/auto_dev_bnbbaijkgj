"""
[PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27] 服务器端冒烟测试
在远程服务器容器内执行 pytest 测试 home_safety 的所有用例，包括新加的 3 个时间格式断言用例。
"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    # 直接在容器里执行 pytest
    cmd = (
        f"docker exec {BACKEND_CONTAINER} sh -c "
        f"'cd /app && python -m pytest tests/test_home_safety_v1.py -v --tb=short -x --no-header 2>&1' "
        f"| tail -80"
    )
    print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=600, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("[stderr]", err)
    rc = stdout.channel.recv_exit_status()
    print(f"\n[exit_code] {rc}")
    client.close()


if __name__ == "__main__":
    main()
