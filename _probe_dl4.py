import paramiko
h="newbb.test.bangbangvip.com"; u="ubuntu"; pw="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h, port=22, username=u, password=pw, timeout=30)
def run(cmd):
    si,so,se=c.exec_command(cmd)
    return so.read().decode("utf-8","replace")+se.read().decode("utf-8","replace")
gw="gateway-nginx"
print("=== container ls /data/static/apk full ===")
print(run("docker exec %s ls -la /data/static/apk/ 2>&1" % gw))
print("=== which historical apk is reachable? check container has the v20260504 apk ===")
print(run("docker exec %s ls -la /data/static/apk/bini_health_android-v20260504-023553-87ac.apk 2>&1" % gw))
print("=== inspect graphdriver / volumes ===")
print(run("docker inspect %s --format '{{json .HostConfig.Binds}} {{json .Config.Volumes}}'" % gw))
print("=== compose file for gateway ===")
print(run("find /home/ubuntu/gateway -maxdepth 2 -name '*.yml' -o -maxdepth 2 -name '*.yaml' 2>/dev/null"))
c.close()
