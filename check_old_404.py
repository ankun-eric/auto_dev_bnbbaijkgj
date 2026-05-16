import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=30, allow_agent=False, look_for_keys=False)
BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'
old_routes = ['/medication-plans', '/health-plan/medications', '/health-plan/medications/add']
for p in old_routes:
    cmd = "curl -sL -o /dev/null -w '%{http_code}' '" + BASE + p + "'"
    _, o, _ = c.exec_command(cmd, timeout=20)
    code = o.read().decode().strip()
    tag = "OK 404" if code == "404" else "WARN (not 404)"
    print(f"  {code}  {BASE}{p}  -> {tag}")
c.close()
