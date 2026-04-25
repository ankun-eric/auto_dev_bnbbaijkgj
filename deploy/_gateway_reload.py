import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
for c in [
    "docker ps --format '{{.Names}}' | grep -i nginx || true",
    "docker ps --format '{{.Names}} {{.Image}}' | grep -iE 'gateway|nginx' || true",
    "docker exec gateway nginx -t 2>&1 | tail -20 || true",
    "docker exec gateway nginx -s reload 2>&1 | tail -10 || true",
]:
    print(f"\n$ {c}")
    _, o, e = ssh.exec_command(c, timeout=30)
    print(o.read().decode(errors='ignore'))
    ee = e.read().decode(errors='ignore')
    if ee.strip(): print('[err]', ee)
ssh.close()
