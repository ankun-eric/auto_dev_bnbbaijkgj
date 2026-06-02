"""安装 pytest 并跑测试。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def run(cmd, timeout=600):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASSWORD, timeout=30)
    try:
        _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        c.close()


print("=== 1. 安装 pytest 等 ===")
code, out, err = run(
    f"docker exec {BACKEND} sh -c 'pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -5'",
    timeout=300,
)
print("EXIT", code)
print(out)
if err:
    print("STDERR:", err[-500:])

print("\n=== 2. 跑 sleep_all_history_fix 测试 ===")
code, out, err = run(
    f"docker exec {BACKEND} sh -c 'cd /app && python -m pytest tests/test_sleep_all_history_fix_v1_20260602.py -v --tb=short --color=no 2>&1' ",
    timeout=600,
)
print("EXIT", code)
print(out[-6000:])
if err:
    print("STDERR:", err[-500:])

print("\n=== 3. 跑 metric_history_row_noaction 测试 ===")
code, out, err = run(
    f"docker exec {BACKEND} sh -c 'cd /app && python -m pytest tests/test_metric_history_row_noaction_v1_20260602.py -v --tb=short --color=no 2>&1' ",
    timeout=600,
)
print("EXIT", code)
print(out[-6000:])
if err:
    print("STDERR:", err[-500:])
