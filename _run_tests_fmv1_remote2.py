# -*- coding: utf-8 -*-
import paramiko, sys
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BE="%s-backend"%DID
TF="test_health_archive_family_member_v1_20260601.py"
def run(c,cmd,t=900):
    print("\n$ "+cmd,flush=True)
    i,o,e=c.exec_command(cmd,timeout=t,get_pty=True)
    out=""
    for line in iter(o.readline,""):
        sys.stdout.write(line); sys.stdout.flush(); out+=line
    rc=o.channel.recv_exit_status(); print("[exit %d]"%rc,flush=True)
    return rc,out
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30)
run(c,"docker exec %s sh -c 'ls /app/tests/conftest.py /app/conftest.py 2>&1; ls /app/*.txt 2>&1'"%BE)
run(c,"docker exec %s sh -c 'pip install -q pytest pytest-asyncio aiosqlite 2>&1 | tail -5; echo DONE'"%BE, t=600)
run(c,"docker exec %s sh -c 'cd /app && python -m pytest tests/%s -v 2>&1 | tail -45'"%(BE,TF),t=600)
c.close()
