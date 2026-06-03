#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在远程后端容器内运行 PRD 相关的 pytest。"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=20)

cmds = [
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "python -m pytest tests/test_glucose_card_optimize_v2.py tests/test_glucose_v1_20260530.py -q --no-header --tb=short 2>&1 | tail -80",
]
for c in cmds:
    print(f"$ {c}\n" + "-" * 40)
    _, out, err = ssh.exec_command(c, timeout=300)
    print(out.read().decode("utf-8", errors="ignore"))
    e = err.read().decode("utf-8", errors="ignore")
    if e:
        print("STDERR:", e)
ssh.close()
