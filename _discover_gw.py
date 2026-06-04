import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=30)
def sh(cmd):
    print("$",cmd); i,o,e=c.exec_command(cmd,timeout=60)
    print(o.read().decode("utf-8","ignore")[-2500:]); 
    er=e.read().decode("utf-8","ignore")
    if er.strip(): print("[err]",er[-600:])
sh("docker exec gateway-nginx nginx -T 2>/dev/null | grep -B1 -A6 downloads | head -40")
sh("docker exec gateway-nginx sh -c 'ls -la /data/static/apk 2>/dev/null | head -8'")
c.close()
