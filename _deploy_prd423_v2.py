#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[PRD-423 v2] 找到正确的项目目录并部署
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import paramiko
from scp import SCPClient

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD  = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)

    def run(cmd, timeout=600):
        print(f"\n>>> {cmd[:300]}")
        sin, sout, serr = cli.exec_command(cmd, timeout=timeout)
        out = sout.read().decode('utf-8', errors='replace')
        err = serr.read().decode('utf-8', errors='replace')
        rc  = sout.channel.recv_exit_status()
        if out: print(out[:8000])
        if err: print("STDERR:", err[:3000])
        return rc, out, err

    # 1. 检查正在运行容器对应的源代码挂载点（uploads 卷）以及 compose 项目名
    run(f"docker inspect {PROJECT_ID}-backend --format='{{{{.Config.Labels}}}}' 2>&1 | tr ',' '\\n' | head -30")
    # compose 项目名
    run(f"docker inspect {PROJECT_ID}-backend --format='{{{{.Config.Labels.com.docker.compose.project}}}}' 2>&1")
    run(f"docker inspect {PROJECT_ID}-backend --format='{{{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}}}' 2>&1")
    # 看 .bak 和非 .bak 的内容差异
    run(f"ls -la /home/ubuntu/{PROJECT_ID}/ 2>/dev/null | head -20")
    run(f"ls -la /home/ubuntu/{PROJECT_ID}.bak/ 2>/dev/null | head -20")
    run(f"ls -la /home/ubuntu/{PROJECT_ID}/h5-web/src/lib/ 2>/dev/null | head -30")
    run(f"ls -la /home/ubuntu/{PROJECT_ID}/h5-web/src/components/ 2>/dev/null | head -30")
    run(f"ls -la /home/ubuntu/{PROJECT_ID}/h5-web/src/components/ai-chat/ 2>/dev/null | head -30")

    cli.close()

if __name__ == "__main__":
    main()
