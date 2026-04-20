import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)
_, o, _ = c.exec_command(
    "ls -la /tmp/bini_health_new.apk /tmp/apk_dl.* 2>&1; "
    "echo '---log---'; "
    "tail -30 /tmp/apk_dl.log 2>&1; "
    "echo '---run.log---'; "
    "tail -30 /tmp/apk_dl.run.log 2>&1; "
    "echo '---running curl---'; "
    "ps aux | grep -E 'curl|dl_apk' | grep -v grep"
)
print(o.read().decode(errors="replace"))
c.close()
