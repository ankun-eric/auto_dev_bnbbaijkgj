#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恢复后端：从镜像层取原始 main.py / __init__.py，避免本地超前源覆盖导致崩溃。"""
import paramiko

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
PID="6b099ed3-7175-4a78-91f4-44570c84ed27"; BE=f"{PID}-backend"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PWD,timeout=30)

def run(cmd,t=300):
    print("$",cmd)
    i,o,e=ssh.exec_command(cmd,timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    if out: print(out.rstrip())
    if err: print("ERR:",err.rstrip())
    return out,err

# 镜像名
img,_=run(f"docker inspect {BE} --format '{{{{.Config.Image}}}}'")
img=img.strip()
print("IMAGE=",img)
# 用镜像起一个临时容器，导出原始 main.py 与 __init__.py
run(f"docker rm -f tmpberecover 2>/dev/null; docker create --name tmpberecover {img}")
run(f"docker cp tmpberecover:/app/app/main.py /tmp/_orig_main.py")
run(f"docker cp tmpberecover:/app/app/api/__init__.py /tmp/_orig_init.py")
run("grep -c bp_v1 /tmp/_orig_init.py")
run("grep -c bp_v1 /tmp/_orig_main.py")
run("grep -c care_card_v1 /tmp/_orig_main.py")
run("wc -l /tmp/_orig_main.py")
ssh.close()
