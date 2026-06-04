#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time, paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
PID="6b099ed3-7175-4a78-91f4-44570c84ed27"; BE=f"{PID}-backend"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PWD,timeout=30)
def run(cmd,t=600):
    print("$",cmd[:100])
    i,o,e=ssh.exec_command(cmd,timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    if out: print(out.rstrip())
    if err: print("ERR:",err.rstrip()[:400])
    return out,err

block = (
    "\n\n# [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式优化：注册个人信息卡/SOS 联系人 API\n"
    "from app.api import care_card_v1 as _care_card_v1  # noqa: E402\n"
    "app.include_router(_care_card_v1.router)\n"
)
# 写入宿主临时文件再 cat 追加到容器内 main.py，规避 shell 转义
with open("_carecard_block.txt","w",encoding="utf-8") as f:
    f.write(block)
sftp=ssh.open_sftp(); sftp.put("_carecard_block.txt","/tmp/_cc_block.txt"); sftp.close()
run(f"docker cp /tmp/_cc_block.txt {BE}:/tmp/_cc_block.txt")
run(f"docker exec {BE} sh -c 'grep -q care_card_v1 /app/app/main.py || cat /tmp/_cc_block.txt >> /app/app/main.py'")
run(f"docker exec {BE} sh -c 'tail -4 /app/app/main.py'")
run(f"docker restart {BE}")
time.sleep(9)
run(f"docker ps --filter name={BE} --format '{{{{.Status}}}}'")
run(f"docker logs --tail 10 {BE} 2>&1 | grep -iE 'error|traceback|importerror|startup complete' | tail")
ssh.close()
