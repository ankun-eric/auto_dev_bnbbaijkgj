import paramiko, json, time

f = open(r'C:\auto_output\bnbbaijkgj\_final_result.txt', 'w')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd, to=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=to)
    return stdout.read().decode() + stderr.read().decode()

f.write("=== Git pull ===\n")
o = run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git fetch origin master && git reset --hard origin/master && git log -1 --oneline', 60)
f.write(o[:500] + '\n')

f.write("=== Restart backend with new TZ ===\n")
o = run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml up -d backend 2>&1', 60)
f.write(o + '\n')

time.sleep(25)

f.write("=== Status ===\n")
raw = run('cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml ps --format json', 30)
for line in raw.split('\n'):
    if line.strip():
        try:
            c = json.loads(line)
            f.write(f"{c['Name']}: {c['State']} health={c.get('Health','?')}\n")
        except: pass

f.write("=== Check TZ in container ===\n")
o = run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c "import datetime; print(datetime.datetime.now()); import time; print(time.tzname)"', 20)
f.write(o + '\n')

f.write("=== Verify server-time (HTTPS) ===\n")
o = run('curl -s --connect-timeout 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/system/server-time 2>&1', 15)
f.write(o + '\n')

f.write("=== Verify health (HTTPS) ===\n")
o = run('curl -s --connect-timeout 10 https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health 2>&1', 15)
f.write(o + '\n')

ssh.close()
f.close()
print('Done')
