#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恢复后端 main.py 至镜像原始版本，并最小化注入 care_card_v1 路由。"""
import os, time, paramiko

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
PID="6b099ed3-7175-4a78-91f4-44570c84ed27"; BE=f"{PID}-backend"
ROOT=os.path.dirname(os.path.abspath(__file__))
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PWD,timeout=30)

def run(cmd,t=600):
    print("$",cmd[:120])
    i,o,e=ssh.exec_command(cmd,timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    if out: print(out.rstrip())
    if err: print("ERR:",err.rstrip()[:500])
    return out,err

# 1) 用镜像原始 main.py 覆盖容器内被污染的 main.py
run(f"docker cp /tmp/_orig_main.py {BE}:/app/app/main.py")

# 2) 在原始 main.py 末尾追加 care_card_v1 路由（幂等：先确保 import 存在于 api 包）
#    care_card_v1.py 自包含（不依赖 app.api.__init__ 导出），直接 import 模块即可
patch = (
    "\\n\\n# [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式优化：注册个人信息卡/SOS 联系人 API\\n"
    "from app.api import care_card_v1 as _care_card_v1  # noqa: E402\\n"
    "app.include_router(_care_card_v1.router)\\n"
)
# 仅当尚未注册时追加
run(f"docker exec {BE} sh -c \"grep -q care_card_v1 /app/app/main.py || printf '{patch}' >> /app/app/main.py\"")

# 3) 重新拷贝 care_card_v1.py 与 home_safety_v1.py（本地版，结构与镜像一致仅改名）
sftp=ssh.open_sftp()
for local, dest in [
    ("backend/app/api/care_card_v1.py", f"{BE}:/app/app/api/care_card_v1.py"),
    ("backend/app/api/home_safety_v1.py", f"{BE}:/app/app/api/home_safety_v1.py"),
    ("backend/tests/test_care_mode_optim_v1_20260531.py", f"{BE}:/app/tests/test_care_mode_optim_v1_20260531.py"),
]:
    tmp=f"/tmp/_re_{os.path.basename(local)}"
    sftp.put(os.path.join(ROOT,local),tmp)
    run(f"docker cp {tmp} {dest}")
    run(f"rm -f {tmp}")
sftp.close()

# 4) 重启 + 等待 + 日志
run(f"docker restart {BE}")
time.sleep(9)
run(f"docker ps --filter name={BE} --format '{{{{.Status}}}}'")
run(f"docker logs --tail 8 {BE} 2>&1 | grep -iE 'error|traceback|importerror|application startup' | tail -8")
ssh.close()
