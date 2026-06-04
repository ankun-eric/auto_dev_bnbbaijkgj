import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
LOCAL = r"C:\auto_output\bnbbaijkgj\_apk_dl\app_20260602_004109_7dki.apk"
FNAME = "app_20260602_004109_7dki.apk"
REMOTE = "/home/ubuntu/" + FNAME

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PWD, timeout=30)

sftp = c.open_sftp()
print("Uploading via SFTP...")
sftp.put(LOCAL, REMOTE)
st = sftp.stat(REMOTE)
print("Uploaded, remote size:", st.st_size)
sftp.close()


def run(cmd, timeout=120):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out, err


out, err = run("docker cp %s gateway-nginx:/data/static/apk/%s" % (REMOTE, FNAME))
print("=== docker cp ===")
print(out, err)

out, err = run("docker exec gateway-nginx sh -c 'chmod 644 /data/static/apk/%s; ls -la /data/static/apk/%s'" % (FNAME, FNAME))
print("=== verify in container ===")
print(out, err)

out, err = run("rm -f " + REMOTE + "; echo cleaned")
print(out, err)

c.close()
