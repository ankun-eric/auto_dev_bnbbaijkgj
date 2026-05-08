#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[PRD-426] 跑关键后端契约回归（确认本次纯前端改动未影响后端接口契约）
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD  = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{PROJECT_ID}-backend"


def run(cli, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    sin, sout, serr = cli.exec_command(cmd, timeout=timeout)
    out = sout.read().decode('utf-8', errors='replace')
    err = serr.read().decode('utf-8', errors='replace')
    rc = sout.channel.recv_exit_status()
    if out: print(out[-6000:])
    if err: print("STDERR:", err[-2000:])
    return rc


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)

    # 容器里装 pytest（一次性）
    run(cli, f"docker exec {BACKEND} pip install --quiet pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -10", timeout=240)

    # 跑与「咨询对象选择 / chat session 创建」相关的回归套件
    cmds = [
        f"docker exec {BACKEND} python -m pytest tests/test_prd420_consult_target_picker.py -q --tb=short 2>&1 | tail -30",
        f"docker exec {BACKEND} python -m pytest tests/test_bug419_chat_sessions.py -q --tb=short 2>&1 | tail -30",
        f"docker exec {BACKEND} python -m pytest tests/test_ai_home_config.py -q --tb=short 2>&1 | tail -30",
    ]
    for cmd in cmds:
        run(cli, cmd, timeout=300)

    cli.close()


if __name__ == "__main__":
    main()
