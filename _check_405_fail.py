import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
_, out, _ = ssh.exec_command(
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -m pytest tests/test_ai_home_config.py::test_t02_admin_put_full --tb=long --no-header -q --disable-warnings 2>&1 | grep -E 'AssertionError|status_code|FAILED|Error|^E |^>'",
    timeout=120,
)
print(out.read().decode("utf-8", "ignore"))
ssh.close()
