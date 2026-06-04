import paramiko
h="newbb.test.bangbangvip.com"; u="ubuntu"; pw="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h, port=22, username=u, password=pw, timeout=30)
def run(cmd):
    si,so,se=c.exec_command(cmd)
    return so.read().decode("utf-8","replace")+se.read().decode("utf-8","replace")
print("=== gateway compose ===")
print(run("cat /home/ubuntu/gateway/docker-compose.yml"))
print("=== conf.d files ===")
print(run("ls -la /home/ubuntu/gateway/conf.d/"))
c.close()
