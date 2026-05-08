"""[Bug-419] 上传更新后的测试并跑完整 9 用例 + 关键回归"""
import paramiko
from pathlib import Path

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)
sftp = ssh.open_sftp()

local = "backend/tests/test_bug419_chat_sessions.py"
remote = f"{PROJECT_DIR}/{local}"
sftp.put(local, remote)
print(f"[uploaded] {local}")
sftp.close()

backend_container = f"{DEPLOY_ID}-backend"
cmd_cp = f"docker cp '{remote}' '{backend_container}:/app/tests/test_bug419_chat_sessions.py'"
stdin, stdout, stderr = ssh.exec_command(cmd_cp)
print(stdout.read().decode())
print(stderr.read().decode())

cmd = (
    f"docker exec {backend_container} bash -c "
    f"'cd /app && pytest tests/test_bug419_chat_sessions.py -v --tb=short 2>&1 | "
    f"grep -v -E \"^(\\.\\.|app/|/usr/|/app/|\\s|-- Docs|warnings)\" | tail -40'"
)
print(f">>> {cmd[:120]}")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
print(stdout.read().decode("utf-8", "replace"))
print("STDERR:", stderr.read().decode("utf-8", "replace"))
ssh.close()
