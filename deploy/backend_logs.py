import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)
si, so, se = c.exec_command("docker logs --tail 100 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -A 30 -E 'tcm|constitution|Traceback|Error' | tail -80", timeout=60)
print(so.read().decode())
print(se.read().decode())
c.close()
