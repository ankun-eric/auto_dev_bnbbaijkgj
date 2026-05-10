import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=30)
stdin, stdout, stderr = c.exec_command(
    "rm -f /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/app_prd442_20260510111718_26db.apk "
    "&& ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/app_prd442_*.apk",
    timeout=30,
)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err:
    print("ERR:", err)
c.close()
