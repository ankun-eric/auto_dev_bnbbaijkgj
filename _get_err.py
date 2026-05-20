import paramiko, time
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888")
i,o,e = ssh.exec_command("docker logs --tail 100 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -60")
print(o.read().decode("utf-8","replace"))
ssh.close()
