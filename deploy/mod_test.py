import paramiko,re
ssh=paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('chat.benne-ai.com',port=22,username='ubuntu',password='Benne-ai@#',timeout=30)
def run(c):
    print('> '+c[:100])
    _,o,e=ssh.exec_command(c,timeout=15,get_pty=True)
    out=o.read().decode();err=e.read().decode()
    r=out+err
    r=re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',r)
    if r.strip(): print(r.strip()[:400])
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
B=DEPLOY_ID+'-backend'
print('=== test1 ===')
run('docker exec '+B+' python -c "import sys; print(sys.path[:3])"')
print('=== test2 ===')
run('docker exec '+B+' python -c "import app; print(1)"')
print('=== test3 ===')
run('docker exec '+B+' python -c "from app.core.database import async_session; print(2)"')
print('=== test4 pwd ===')
run('docker exec '+B+' pwd')
print('=== test5 ls ===')
run('docker exec '+B+' ls /app/app/core/database.py')
ssh.close()
print('done')
