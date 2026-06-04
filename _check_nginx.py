import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=20)
for cmd in [
    "ls /etc/nginx/sites-available/ 2>/dev/null; ls /etc/nginx/conf.d 2>/dev/null",
    "sudo -n cat /etc/nginx/sites-available/autodev 2>/dev/null | head -60",
    "sudo -n grep -l '6b099ed3' /etc/nginx -r 2>/dev/null",
]:
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip(): print("[err]", err)
c.close()
