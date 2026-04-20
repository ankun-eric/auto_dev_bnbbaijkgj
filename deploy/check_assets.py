import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
_, o, _ = c.exec_command(
    f"ls -la {PROJ}/static/apk/ | tail -20; "
    f"echo '---downloads---'; "
    f"ls -la {PROJ}/static/downloads/ | tail -20; "
)
print(o.read().decode(errors="replace"))
c.close()
