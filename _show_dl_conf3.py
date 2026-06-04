import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com',username='ubuntu',password='Newbang888',timeout=30)
def run(cmd):
    i,o,e=c.exec_command(cmd,timeout=60); return o.read().decode('utf-8','ignore'),e.read().decode('utf-8','ignore')
o,e=run("docker exec gateway-nginx cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf")
print("=== CONF (in container) ===\n", o, e)
# host gateway dir
o,e=run("ls -la /home/ubuntu/gateway/conf.d/ | grep 6b099")
print("=== host conf.d listing ===\n", o, e)
c.close()
