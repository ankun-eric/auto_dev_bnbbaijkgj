import paramiko, json, time, traceback

f = open(r'C:\auto_output\bnbbaijkgj\_rebuild_fr_result.txt', 'w')

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

    def run(cmd, to=60):
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=to)
        return stdout.read().decode() + stderr.read().decode()

    f.write("=== Rebuild admin-web ===\n")
    o = run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -15', 120)
    f.write(o[:1000] + '\n')

    f.write("=== Rebuild h5-web ===\n")
    o = run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -15', 120)
    f.write(o[:1000] + '\n')

    f.write("=== Restart ===\n")
    o = run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml up -d 2>&1', 60)
    f.write(o + '\n')

    time.sleep(15)

    f.write("=== Status ===\n")
    raw = run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml ps --format json', 30)
    for line in raw.split('\n'):
        if line.strip():
            try:
                c = json.loads(line)
                f.write(f"{c['Name']}: {c['State']} health={c.get('Health','?')}\n")
            except: pass

    f.write("=== Verify server-time ===\n")
    o = run('curl -s --connect-timeout 10 http://localhost:8000/api/system/server-time 2>&1', 15)
    f.write(o + '\n')

    f.write("=== Verify health ===\n")
    o = run('curl -s --connect-timeout 10 http://localhost:8000/api/health 2>&1', 15)
    f.write(o + '\n')

    ssh.close()
except Exception as e:
    f.write(f'ERROR: {e}\n{traceback.format_exc()}\n')

f.close()
print('Done, results in _rebuild_fr_result.txt')
