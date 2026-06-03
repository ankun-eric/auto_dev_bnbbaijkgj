import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect(HOST, username=USER, password=PWD, timeout=30)
def r(cmd, t=600):
  i,o,e=c.exec_command(cmd, timeout=t)
  out=o.read().decode('utf-8','replace'); err=e.read().decode('utf-8','replace')
  print(out + (('\n[stderr]\n'+err) if err.strip() else ''))
  print('exit=', o.channel.recv_exit_status())
r('docker exec ' + DEPLOY_ID + '-backend pip install pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -8', 300)
r('docker exec ' + DEPLOY_ID + '-backend bash -c "cd /app && python -m pytest tests/test_member_center_v2.py -v --tb=short 2>&1 | tail -120"', 300)
c.close()
