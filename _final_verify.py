import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)
def run(c):
    print('>>>',c[:200])
    _,o,e=s.exec_command(c, timeout=60)
    print(o.read().decode('utf-8','replace')[-2000:])
    err=e.read().decode('utf-8','replace')
    if err: print('ERR:',err[-500:])
    print('exit=',o.channel.recv_exit_status(),'\n')
BASE=f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
run(f'curl -sLk -o /dev/null -w "health-profile=%{{http_code}}\\n" {BASE}/health-profile')
run(f'curl -sLk -o /dev/null -w "api/health-profile/self(no-auth)=%{{http_code}}\\n" {BASE}/api/health-profile/self')
run(f'docker ps --format "{{{{.Names}}}}\t{{{{.Status}}}}" | grep 6b099ed3')
s.close()
