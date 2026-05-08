#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""[BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v2.0]
在远程 backend 容器内跑 v1 已建立的回归测试，确认后端契约仍然稳定。
"""
import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    sys.stdout.flush()
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}", file=sys.stderr)
    print(f"[exit={rc}]")
    sys.stdout.flush()
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    backend = f"{DEPLOY_ID}-backend"
    try:
        # 列出 reschedule 相关的测试文件
        run(client, f"docker exec {backend} ls -la /app/tests/ 2>&1 | grep -i reschedul")
        # 跑 v1 已建立的"reschedule popup auto close"回归测试
        run(
            client,
            f"docker exec {backend} bash -c 'cd /app && python -m pytest tests/test_bugfix_reschedule_popup_auto_close.py -v --tb=short 2>&1 | tail -80'",
            timeout=600,
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
