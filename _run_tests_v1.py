"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1] 安装 pytest 并运行测试"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{DEPLOY_ID}-backend"


cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=60,
            look_for_keys=False, allow_agent=False)


def run(cmd, timeout=600):
    print(f"\n$ {cmd[:240]}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-8000:])
    if err.strip():
        print(f"[err] {err[-2000:]}")
    print(f"[rc={rc}]")
    return rc, out, err


# 1. 安装 pytest + aiosqlite + pytest-asyncio
run(f"docker exec {BE} pip install --no-cache-dir -q pytest pytest-asyncio aiosqlite 2>&1 | tail -10", timeout=300)

# 2. 跑指定测试
run(f"docker exec {BE} sh -c 'cd /app && python -m pytest tests/test_guardian_bugfix_v1_20260529.py -v --tb=short --no-header 2>&1'",
    timeout=900)

cli.close()
