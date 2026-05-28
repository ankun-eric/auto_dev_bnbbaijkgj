#!/usr/bin/env python3
"""上传更新后的测试 + 跑回归"""
import paramiko, os, sys

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
LOCAL_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    # 上传更新后的旧测试
    local = os.path.join(LOCAL_ROOT, 'backend', 'tests', 'test_guardian_system_v13.py')
    remote = f'{PROJECT_DIR}/backend/tests/test_guardian_system_v13.py'
    print(f"upload {local} -> {remote}")
    sftp.put(local, remote)

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

    # docker cp 进容器
    run(f'docker cp {PROJECT_DIR}/backend/tests/test_guardian_system_v13.py 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/tests/test_guardian_system_v13.py')

    # 跑全部相关回归
    out, err, code = run(
        'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -lc "cd /app && python -m pytest tests/test_guardian_system_v13.py tests/test_guardian_system_v131.py tests/test_iguard_v2.py tests/test_reverse_guardian.py tests/test_my_guardian_card_bugfix_20260528.py -v --tb=short 2>&1 | tail -100"',
        timeout=420,
    )
    ssh.close()
    sys.exit(0 if 'failed' not in out or '0 failed' in out else 1)

if __name__ == '__main__':
    main()
