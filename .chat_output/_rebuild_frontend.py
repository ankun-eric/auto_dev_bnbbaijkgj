import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
cmd = "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose up -d --build --force-recreate admin-web h5-web"
print("Running:", cmd[:200])
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=900)
code = stdout.channel.recv_exit_status()
print("exit:", code)
print("stdout:", stdout.read().decode("utf-8", errors="replace")[-2000:])
print("stderr:", stderr.read().decode("utf-8", errors="replace")[-2000:])
ssh.close()
