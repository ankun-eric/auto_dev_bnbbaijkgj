import paramiko, time
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
BE=f'{DEPLOY_ID}-backend'
PROJ=f'/home/ubuntu/{DEPLOY_ID}'

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=60,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=120):
    si,so,se=cli.exec_command(cmd,timeout=timeout)
    out=so.read().decode(errors='replace'); err=se.read().decode(errors='replace'); rc=so.channel.recv_exit_status()
    print('$',cmd[:200]); 
    if out.strip(): print(out[-5000:])
    if err.strip(): print('STDERR:',err[-1000:])
    print('rc=',rc); return rc, out

r(f'docker ps --format "{{{{.Names}}}}|{{{{.Status}}}}" | grep {DEPLOY_ID}')
print("\n=== logs (last 80) ===")
r(f'docker logs --tail 80 {BE} 2>&1')
print("\n=== Check pytest in container ===")
time.sleep(5)
r(f'docker exec {BE} which python')
r(f'docker exec {BE} python -m pytest --version')

cli.close()
