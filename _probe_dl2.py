import paramiko
h="newbb.test.bangbangvip.com"; u="ubuntu"; pw="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h, port=22, username=u, password=pw, timeout=30)
def run(cmd):
    si,so,se=c.exec_command(cmd)
    return so.read().decode("utf-8","replace")+se.read().decode("utf-8","replace")
gw="gateway-nginx"
print("=== full mounts (all) ===")
print(run("docker inspect %s --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'" % gw))
print("=== list /data/static/apk in container ===")
print(run("docker exec %s ls -la /data/static/apk/ 2>&1 | head -30" % gw))
c.close()
