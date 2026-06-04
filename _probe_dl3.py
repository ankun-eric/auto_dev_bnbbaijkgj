import paramiko
h="newbb.test.bangbangvip.com"; u="ubuntu"; pw="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h, port=22, username=u, password=pw, timeout=30)
def run(cmd):
    si,so,se=c.exec_command(cmd)
    return so.read().decode("utf-8","replace")+se.read().decode("utf-8","replace")
gw="gateway-nginx"
print("=== inspect Mounts json full ===")
print(run("docker inspect %s --format '{{json .Mounts}}'" % gw))
print("=== find on host /data/static/apk ===")
print(run("ls -la /data/static/apk/ 2>&1 | head; echo '---'; sudo ls -la /data/static/apk/ 2>&1 | head"))
print("=== find existing apk zip on host ===")
print(run("find / -name 'miniprogram_20260601_232958_35ff.zip' 2>/dev/null"))
c.close()
