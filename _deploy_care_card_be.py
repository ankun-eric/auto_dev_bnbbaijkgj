#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[PRD-CARE-MODE-OPTIM-V1] 部署关怀模式后端改动 + 运行测试"""
import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{PID}-backend"
ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ = f"/home/ubuntu/{PID}"

FILES = [
    ("backend/app/api/care_card_v1.py", "app/api/care_card_v1.py"),
    ("backend/app/api/home_safety_v1.py", "app/api/home_safety_v1.py"),
    ("backend/app/main.py", "app/main.py"),
    ("backend/tests/test_care_mode_optim_v1_20260531.py", "tests/test_care_mode_optim_v1_20260531.py"),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30)
sftp = ssh.open_sftp()


def run(cmd, timeout=600):
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out.rstrip())
    if err:
        print("STDERR:", err.rstrip())
    return out, err


# 1. 上传到服务器项目目录，再 docker cp 进容器
for local, rel in FILES:
    lp = os.path.join(ROOT, local)
    remote_tmp = f"/tmp/_carecard_{os.path.basename(rel)}"
    print(f">>> upload {local}")
    sftp.put(lp, remote_tmp)
    # 同步到服务器项目目录（保持 git/源一致）
    run(f"cp {remote_tmp} {PROJ}/backend/{rel} 2>/dev/null || mkdir -p {PROJ}/backend/$(dirname {rel}) && cp {remote_tmp} {PROJ}/backend/{rel}")
    run(f"docker cp {remote_tmp} {BE}:/app/{rel}")
    run(f"rm -f {remote_tmp}")

sftp.close()

# 2. 重启后端
print(">>> restart backend")
run(f"docker restart {BE}")
import time
time.sleep(8)
run(f"docker logs --tail 20 {BE}")

# 3. 容器内跑测试
print(">>> run pytest in container")
run(f"docker exec {BE} sh -c 'cd /app && python -m pytest tests/test_care_mode_optim_v1_20260531.py -q 2>&1 | tail -30'", timeout=600)

ssh.close()
print(">>> backend deploy DONE")
