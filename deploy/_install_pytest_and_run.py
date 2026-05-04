"""容器内安装 pytest 并跑回归测试。"""
import sys, time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
BACKEND = '6b099ed3-7175-4a78-91f4-44570c84ed27-backend'


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=600, ignore_error=False):
    print(f"\n>>> {cmd}", flush=True)
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    while True:
        if chan.recv_ready():
            sys.stdout.write(chan.recv(4096).decode('utf-8', errors='replace'))
            sys.stdout.flush()
        if chan.recv_stderr_ready():
            sys.stdout.write(chan.recv_stderr(4096).decode('utf-8', errors='replace'))
            sys.stdout.flush()
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"[exit_code: {code}]")
    return code


def main():
    ssh = get_ssh()
    try:
        # 安装 pytest（参考既有脚本）
        run(
            ssh,
            f'docker exec {BACKEND} pip install --no-cache-dir '
            f'pytest pytest-asyncio aiosqlite httpx '
            f'-i https://mirrors.cloud.tencent.com/pypi/simple '
            f'--trusted-host mirrors.cloud.tencent.com --timeout 120',
            timeout=300,
        )
        # 跑回归测试
        run(
            ssh,
            f'docker exec {BACKEND} python -m pytest '
            f'tests/test_contact_store_storeid_bugfix.py '
            f'-v --tb=short -p no:cacheprovider 2>&1',
            timeout=300,
        )
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
