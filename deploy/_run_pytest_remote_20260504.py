#!/usr/bin/env python3
"""在 backend 容器内安装 pytest 并运行新增的测试。"""
import io
import sys
import time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BACKEND = f'{PROJECT_ID}-backend'


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=600):
    print(f"\n>>> {cmd}")
    sys.stdout.flush()
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out_buf = io.StringIO()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_buf.write(data)
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_buf.write(data)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"[exit_code: {code}]")
    return out_buf.getvalue(), code


def main():
    ssh = get_ssh()
    try:
        # 安装 pytest 与 aiosqlite（测试 conftest 用了 sqlite）
        run(ssh,
            f'docker exec {BACKEND} pip install --no-cache-dir '
            f'pytest pytest-asyncio aiosqlite '
            f'-i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com --timeout 120',
            timeout=300)

        # 跑新增测试
        out, code = run(ssh,
            f'docker exec {BACKEND} python -m pytest '
            f'tests/test_orders_statistics_alignment.py '
            f'tests/test_fulfillment_label_dict.py '
            f'-v --tb=short --no-header -p no:cacheprovider 2>&1',
            timeout=600)

        # 总结
        print("\n=== 测试结束 ===")
        if code == 0:
            print("ALL_GREEN")
        else:
            print(f"FAILED_EXIT_{code}")

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
