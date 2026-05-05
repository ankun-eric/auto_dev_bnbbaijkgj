import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf",
    "ls /home/ubuntu/gateway/conf.d/gateway-routes/",
    "cat /home/ubuntu/gateway/conf.d/gateway-routes/6b099ed3-7175-4a78-91f4-44570c84ed27-apk.conf",
    "ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram/ | head -20",
]

for c in cmds:
    print("=" * 80)
    print("$", c)
    _, out, err = ssh.exec_command(c, timeout=30)
    o = out.read().decode(errors="replace")
    e = err.read().decode(errors="replace")
    if o: print(o)
    if e: print("ERR:", e)

ssh.close()
