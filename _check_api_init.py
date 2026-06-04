import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd):
    print('>>>', cmd[:200])
    _,o,e=s.exec_command(cmd, timeout=60)
    out=o.read().decode('utf-8','replace'); err=e.read().decode('utf-8','replace')
    print(out[-3000:])
    if err: print('ERR:', err[-1000:])
    print('exit=', o.channel.recv_exit_status())

run(f'docker exec {DEPLOY_ID}-backend bash -c "wc -l /app/app/api/__init__.py && head -60 /app/app/api/__init__.py"')
run(f'docker exec {DEPLOY_ID}-backend bash -c "ls -la /app/app/api/health_profile_self.py"')
run(f'docker exec {DEPLOY_ID}-backend bash -c "python -c \\"from app.api import health_profile_self; print(health_profile_self.router)\\" 2>&1"')
s.close()
