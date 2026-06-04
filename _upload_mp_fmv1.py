# -*- coding: utf-8 -*-
import os, paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BE="%s-backend"%DID
BASE="https://newbb.test.bangbangvip.com/autodev/%s"%DID
ROOT=os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT,"_mp_fmv1_zip_name.txt")) as f: ZIP=f.read().strip()
local=os.path.join(ROOT,ZIP); remote="/home/ubuntu/%s/%s"%(DID,ZIP)
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30)
def run(cmd,t=300):
    i,o,e=c.exec_command(cmd,timeout=t); return o.channel.recv_exit_status(),o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
sftp=c.open_sftp(); sftp.put(local,remote); sftp.close(); print("[sftp]",remote)
print(run("docker cp %s %s:/app/uploads/%s"%(remote,BE,ZIP))[0])
print("[verify]",run("docker exec %s ls -l /app/uploads/%s"%(BE,ZIP))[1].strip())
run("rm -f %s"%remote)
c.close()
print("\nDOWNLOAD_URL=%s/uploads/%s"%(BASE,ZIP))
