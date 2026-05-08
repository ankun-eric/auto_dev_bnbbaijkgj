import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
stdin, stdout, stderr = ssh.exec_command("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -m pytest tests/test_ai_home_config.py::test_t02_admin_put_full -x 2>&1", timeout=120)
out = stdout.read().decode("utf-8", "ignore")
print(out)
ssh.close()
