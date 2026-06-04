import paramiko, os
h="newbb.test.bangbangvip.com"; u="ubuntu"; pw="Newbang888"
fname="app_20260602_000037_fd67.apk"
local=os.path.join("_apk_dl", fname)
remote_tmp="/home/ubuntu/tmp_apk/"+fname
gw="gateway-nginx"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h, port=22, username=u, password=pw, timeout=60)
def run(cmd):
    si,so,se=c.exec_command(cmd)
    out=so.read().decode("utf-8","replace"); err=se.read().decode("utf-8","replace")
    return out+err
run("mkdir -p /home/ubuntu/tmp_apk")
sftp=c.open_sftp()
print("Uploading %s (%d bytes)..." % (fname, os.path.getsize(local)))
sftp.put(local, remote_tmp)
print("Uploaded. remote size:", sftp.stat(remote_tmp).st_size)
sftp.close()
print("=== docker cp into gateway container ===")
print(run("docker cp %s %s:/data/static/apk/%s" % (remote_tmp, gw, fname)))
print("=== verify in container ===")
print(run("docker exec %s ls -la /data/static/apk/%s" % (gw, fname)))
print("=== cleanup tmp ===")
print(run("rm -f %s" % remote_tmp))
c.close()
print("DONE")
