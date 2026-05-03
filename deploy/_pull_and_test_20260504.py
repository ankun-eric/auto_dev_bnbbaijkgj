#!/usr/bin/env python3
"""服务器仓库拉取最新代码 -> 重启 backend -> 安装 pytest -> 运行测试。"""
import io, sys, time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{PROJECT_ID}'
BACKEND = f'{PROJECT_ID}-backend'


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=600):
    print(f"\n>>> {cmd}", flush=True)
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    while True:
        if chan.recv_ready():
            sys.stdout.write(chan.recv(4096).decode('utf-8', errors='replace')); sys.stdout.flush()
        if chan.recv_stderr_ready():
            sys.stdout.write(chan.recv_stderr(4096).decode('utf-8', errors='replace')); sys.stdout.flush()
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"[exit_code: {code}]")
    return code


def main():
    ssh = get_ssh()
    try:
        # 拉取 master 最新
        run(ssh, f'cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline')

        # 用挂载方式直接把仓库 backend 目录复制到容器内（覆盖测试文件）
        run(ssh, f'docker cp {PROJECT_DIR}/backend/tests {BACKEND}:/app/')

        # 也把 admin-web/h5-web/miniprogram/flutter_app 目录复制进去（让 fulfillment 字典测试能找到目录）
        for d in ('admin-web', 'h5-web', 'miniprogram', 'flutter_app'):
            run(ssh, f'docker exec {BACKEND} mkdir -p /repo')
            run(ssh, f'docker cp {PROJECT_DIR}/{d} {BACKEND}:/repo/')

        # 安装 pytest
        run(ssh,
            f'docker exec {BACKEND} pip install --no-cache-dir pytest pytest-asyncio aiosqlite '
            f'-i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com --timeout 120',
            timeout=300)

        # 跑订单统计测试
        run(ssh,
            f'docker exec {BACKEND} python -m pytest tests/test_orders_statistics_alignment.py '
            f'-v --tb=short -p no:cacheprovider 2>&1',
            timeout=600)

        # 跑 fulfillment label 字典测试，传 REPO_ROOT 指向已复制的目录
        # 但目录复制到 /repo/admin-web/, 测试期望 REPO_ROOT/admin-web 等存在
        run(ssh,
            f'docker exec -e REPO_ROOT=/repo {BACKEND} python -m pytest tests/test_fulfillment_label_dict.py '
            f'-v --tb=short -p no:cacheprovider 2>&1',
            timeout=300)

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
