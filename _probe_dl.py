import paramiko
h="newbb.test.bangbangvip.com"; u="ubuntu"; pw="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h, port=22, username=u, password=pw, timeout=30)
def run(cmd):
    si,so,se=c.exec_command(cmd)
    return so.read().decode("utf-8","replace")+se.read().decode("utf-8","replace")
print("=== gateway container ===")
print(run("docker ps --format '{{.Names}}' | grep -i gateway"))
gw=run("docker ps --format '{{.Names}}' | grep -i gateway").strip().splitlines()
gw=gw[0] if gw else ""
print("GW=",gw)
print("=== nginx downloads location ===")
print(run("docker exec %s nginx -T 2>/dev/null | grep -i -A6 downloads" % gw))
print("=== mounts ===")
print(run("docker inspect %s --format '{{json .Mounts}}'" % gw))
c.close()
