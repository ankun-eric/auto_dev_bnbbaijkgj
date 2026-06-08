import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('chat.benne-ai.com', 22, 'ubuntu', 'Benne-ai@#', timeout=20, allow_agent=False, look_for_keys=False)
stdin, stdout, stderr = c.exec_command('curl -s https://chat.benne-ai.com/server-time', timeout=20)
print("stdout:", stdout.read().decode())
print("stderr:", stderr.read().decode())
c.close()
