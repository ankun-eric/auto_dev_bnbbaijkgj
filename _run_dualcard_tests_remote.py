"""[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 在远程服务器 Docker 容器中跑后端自动化测试。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)


def run(cmd, timeout=600):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print("STDERR:", err)
    print(f"[exit={code}]")
    return code, out, err


# 0. 安装 pytest（如已安装则忽略）
run(
    f"docker exec {DEPLOY_ID}-backend "
    f"pip install --quiet pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -5",
    timeout=180,
)

# 1. 新增的双卡片测试
run(
    f"docker exec {DEPLOY_ID}-backend python -m pytest "
    f"tests/test_guardian_dualcard_v1_20260528.py --tb=short -q 2>&1 | tail -50",
    timeout=300,
)

# 2. 回归反向守护接口（旧测试）
run(
    f"docker exec {DEPLOY_ID}-backend python -m pytest "
    f"tests/test_reverse_guardian.py --tb=short -q 2>&1 | tail -30",
    timeout=300,
)

client.close()
