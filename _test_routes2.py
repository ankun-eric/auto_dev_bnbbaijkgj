import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888")
cmd = (
    "for p in / /health-profile /health-profile/i-guard /health-profile/my-guardians "
    "/member-center /ai-home; do "
    "code=$(curl -sk -L -o /dev/null -w '%{http_code}' http://192.168.32.5:3001$p); "
    "echo \"$p: $code\"; done"
)
i, o, e = c.exec_command(cmd, timeout=30)
print(o.read().decode())
c.close()
