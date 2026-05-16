import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com',22,'ubuntu','Newbang888',timeout=30)
CTR='6b099ed3-7175-4a78-91f4-44570c84ed27-h5'
for cmd in [
    f"docker exec {CTR} ls /app 2>&1 | head -30",
    f"docker exec {CTR} ls /app/src/app 2>&1 | head -10",
    f"docker exec {CTR} find /app -name 'page.tsx' -path '*ai-home*' 2>&1 | head -5",
    f"docker exec {CTR} ls /app/.next 2>&1 | head -5",
]:
    _, o, _ = c.exec_command(cmd, timeout=20)
    print('$', cmd); print(o.read().decode()[:500]); print()
c.close()
