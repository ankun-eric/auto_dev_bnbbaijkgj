# -*- coding: utf-8 -*-
import paramiko, sys

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ="/home/ubuntu/%s"%DID
BE="%s-backend"%DID
TF="test_health_archive_family_member_v1_20260601.py"

def run(c,cmd,t=600):
    print("\n$ "+cmd,flush=True)
    i,o,e=c.exec_command(cmd,timeout=t,get_pty=True)
    out=""
    for line in iter(o.readline,""):
        sys.stdout.write(line); sys.stdout.flush(); out+=line
    rc=o.channel.recv_exit_status(); print("[exit %d]"%rc,flush=True)
    return rc,out

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30)
# 拷测试文件进容器
run(c,"docker cp %s/backend/tests/%s %s:/app/tests/%s && echo copied"%(PROJ,TF,BE,TF))
# 跑测试
run(c,"docker exec %s sh -c 'cd /app && python -m pytest tests/%s -v 2>&1 | tail -40'"%(BE,TF),t=600)
c.close()
