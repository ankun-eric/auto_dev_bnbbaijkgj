import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

cmds = [
    'docker ps --format "{{.Names}}\t{{.Image}}" | grep -i -E "gateway|nginx" || true',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls /app/tests/ | head -80',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -c "ls /app/tests/test_contact_store_storeid_bugfix.py 2>&1 || echo NOT_FOUND"',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -c "find /app -name test_contact_store_storeid_bugfix.py 2>/dev/null || echo NOT_FOUND"',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -c "python -c \'import urllib.request; r=urllib.request.urlopen(\\\"http://localhost:8000/api/health\\\",timeout=5); print(r.status, r.read()[:200])\'"',
]
for cmd in cmds:
    print('\n>>>', cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(out)
    if err:
        print('STDERR:', err)
ssh.close()
