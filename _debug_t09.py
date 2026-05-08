"""[Bug-419 debug] 单独运行 T09 测试，获取完整失败信息"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

cmd = (
    f"docker exec {DEPLOY_ID}-backend bash -c "
    f"'cd /app && pytest tests/test_bug419_chat_sessions.py::test_t09_default_family_member_fallback "
    f"-v --tb=long 2>&1 | grep -v -E \"^(\\.\\.|app/|/usr/|/app/|\\s|-- Docs|warnings|Pydantic)\" | tail -80'"
)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
print(stdout.read().decode("utf-8", "replace"))
print("STDERR:", stderr.read().decode("utf-8", "replace"))
ssh.close()
