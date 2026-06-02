"""在 backend 容器内运行睡眠全部历史修复 + metric history noaction 测试。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND = f"{DEPLOY_ID}-backend"


def run(cmd, timeout=600):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        c.close()


cmd = (
    f"docker exec {BACKEND} sh -c 'cd /app && "
    "python -m pytest tests/test_sleep_all_history_fix_v1_20260602.py "
    "tests/test_metric_history_row_noaction_v1_20260602.py "
    "-v --tb=short --color=no 2>&1' | tail -120"
)
print(f"CMD: {cmd}\n")
code, out, err = run(cmd, timeout=600)
print(f"EXIT {code}")
print(out)
if err:
    print("--- STDERR ---")
    print(err[-2000:])
