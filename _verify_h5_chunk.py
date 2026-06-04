# -*- coding: utf-8 -*-
import paramiko, sys
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
H5="%s-h5"%DID
def run(c,cmd,t=120):
    print("\n$ "+cmd,flush=True)
    i,o,e=c.exec_command(cmd,timeout=t,get_pty=True)
    out=""
    for line in iter(o.readline,""):
        sys.stdout.write(line); sys.stdout.flush(); out+=line
    o.channel.recv_exit_status()
    return out
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30)
# 找 archive-list 相关 chunk 并 grep 关键文案
run(c, "docker exec %s sh -c \"grep -rl '暂无家庭成员' /app/.next 2>/dev/null | head; echo '---count---'; grep -rl '暂无家庭成员' /app/.next 2>/dev/null | wc -l\""%H5)
run(c, "docker exec %s sh -c \"grep -rl 'NewFamilyMemberModal\\|新增咨询人' /app/.next/server/app/health-profile 2>/dev/null | head; echo ok\""%H5)
c.close()
