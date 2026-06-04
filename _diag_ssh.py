# -*- coding: utf-8 -*-
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"; PROJ=f"/home/ubuntu/{DEPLOY_ID}"
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=30)
def run(cmd,t=120):
    print("\n$",cmd,flush=True)
    i,o,e=cli.exec_command(cmd,timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    print(out,flush=True)
    if err: print("[err]",err,flush=True)
    return out
run(f"cd {PROJ} && git log -1 --oneline")
run(f"cd {PROJ} && git remote -v")
cli.close(); print("\nDIAG DONE",flush=True)
