import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=30)
i, o, e = ssh.exec_command("cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf")
print(o.read().decode("utf-8", errors="replace"))
ssh.close()
