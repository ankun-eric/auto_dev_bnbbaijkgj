#!/usr/bin/env python3
"""[BUGFIX-MY-GUARDIAN-CARD-20260528] 服务器上跑 pytest"""
import paramiko, sys

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    def run(cmd, timeout=600):
        print(f"\n>>> {cmd[:200]}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        code = stdout.channel.recv_exit_status()
        if out: print(out[-5000:])
        if err: print(f"STDERR: {err[-2000:]}")
        print(f"[exit={code}]")
        return out, err, code

    # 1) 安装 pytest 与依赖
    run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -lc "pip install --quiet pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -5"', 240)

    # 2) 跑测试（如果项目有 conftest 用 SQLite）
    out, err, code = run(
        'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -lc "cd /app && python -m pytest tests/test_my_guardian_card_bugfix_20260528.py -v --tb=short 2>&1 | tail -150"',
        timeout=420,
    )

    # 3) 同时跑回归（守护人 v13/v131 + reverse_guardian + i-guard v2）
    print("\n========== 回归测试 ==========")
    run(
        'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -lc "cd /app && python -m pytest tests/test_guardian_system_v13.py tests/test_guardian_system_v131.py tests/test_iguard_v2.py tests/test_reverse_guardian.py -v --tb=line 2>&1 | tail -80"',
        timeout=420,
    )

    ssh.close()
    sys.exit(0 if code == 0 else 1)

if __name__ == '__main__':
    main()
