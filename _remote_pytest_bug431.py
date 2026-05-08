"""[Bug-431] 远程关键回归 pytest（补装 aiosqlite 后跑 3 套）。"""
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASSWORD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

CONTAINER = f"{DEPLOY_ID}-backend"

# 0. 补装 aiosqlite + 其他可能缺失的依赖
install = (f"docker exec {CONTAINER} sh -c "
           "'pip install -q aiosqlite -i https://pypi.tuna.tsinghua.edu.cn/simple "
           "--trusted-host pypi.tuna.tsinghua.edu.cn 2>&1 | tail -5'")
print(f">>> {install}")
_, out, err = ssh.exec_command(install, timeout=120)
print(out.read().decode("utf-8","replace"))

# 跑测试
TEST_TARGETS = [
    "tests/test_prd420_consult_target_picker.py",
    "tests/test_bug419_chat_sessions.py",
    "tests/test_ai_home_config.py",
]
target_str = " ".join(TEST_TARGETS)
cmd = f"docker exec {CONTAINER} sh -c 'cd /app && python -m pytest {target_str} -v --tb=short 2>&1 | tail -150'"
print(f"\n>>> {cmd}")
_, out, err = ssh.exec_command(cmd, timeout=600)
print(out.read().decode("utf-8","replace"))
ssh.close()
