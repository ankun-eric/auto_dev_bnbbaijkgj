import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd):
    print(f"\n$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode('utf-8', 'replace')
    err = e.read().decode('utf-8', 'replace')
    print(out)
    if err.strip():
        print('STDERR:', err)

run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git remote -v")
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git fetch origin master --depth 5 2>&1 | tail -10")
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git log --all -3 --oneline")
run("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git reset --hard origin/master && git log -3 --oneline")
c.close()
