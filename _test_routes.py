import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888")
cmd = (
    "for p in /h5/health-profile /h5/health-profile/i-guard /h5/health-profile/my-guardians "
    "/h5/member-center /h5/ai-home /h5/ /h5; do "
    "code=$(curl -sk -L -o /dev/null -w '%{http_code}' http://192.168.32.5:3001$p); "
    "echo \"$p: $code\"; done"
)
i, o, e = c.exec_command(cmd, timeout=30)
print(o.read().decode())
print("[err]", e.read().decode())
c.close()
