import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
def run(cmd):
    c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST,username=USER,password=PWD,timeout=20,look_for_keys=False,allow_agent=False)
    _,o,e=c.exec_command(cmd,timeout=60); return o.read().decode(),e.read().decode()
B = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cmds = [
    f"curl -sI '{B}/app_prd440_20260510014236_5145.apk'",
    f"docker exec {DEPLOY_ID}-h5 sh -c 'find / -name app_prd440_20260510014236_5145.apk 2>/dev/null'",
    f"docker inspect {DEPLOY_ID}-backend --format '{{{{json .Mounts}}}}' | python3 -m json.tool",
    # backend likely serves /uploads/ AND/OR has the project root mounted; let's verify file existence inside backend
    f"docker exec {DEPLOY_ID}-backend sh -c 'ls -la /uploads/ 2>&1 | head -20'",
    # Check if backend has a catch-all that serves files from /uploads or project root
    f"docker exec {DEPLOY_ID}-backend sh -c 'find / -name app_prd440_20260510014236_5145.apk 2>/dev/null | head'",
]
for c in cmds:
    print('\n$ '+c); o,e=run(c); print(o)
    if e.strip(): print('[ERR]',e)
