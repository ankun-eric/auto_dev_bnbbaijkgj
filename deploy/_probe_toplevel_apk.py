import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
def run(cmd):
    c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST,username=USER,password=PWD,timeout=20,look_for_keys=False,allow_agent=False)
    _,o,e=c.exec_command(cmd,timeout=60); return o.read().decode(),e.read().decode()
cmds = [
    f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}-toplevel-apk.conf",
]
for c in cmds:
    print('\n$ '+c); o,e=run(c); print(o)
    if e.strip(): print('[ERR]',e)
