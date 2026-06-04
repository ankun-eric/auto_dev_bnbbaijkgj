import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASSWORD='Newbang888'
REMOTE_BASE='/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
cmds = [
    f"cat {REMOTE_BASE}/docker-compose.yml | head -60",
    f"docker compose -f {REMOTE_BASE}/docker-compose.yml exec -T backend wc -l /app/tests/test_home_safety_v2_revision.py",
    f"docker compose -f {REMOTE_BASE}/docker-compose.yml exec -T backend sed -n '60,68p' /app/tests/test_home_safety_v2_revision.py",
]
for cmd in cmds:
    print("$", cmd)
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8","replace"))
    err = e.read().decode("utf-8","replace")
    if err: print("[err]", err)
c.close()
