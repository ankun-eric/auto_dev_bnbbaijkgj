import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASSWORD='Newbang888'
REMOTE_BASE='/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
cmd = "cat /tmp/o.txt"
_, o, _ = c.exec_command(cmd, timeout=60)
print(o.read().decode("utf-8","replace"))
c.close()
