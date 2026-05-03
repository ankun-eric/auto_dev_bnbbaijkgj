#!/usr/bin/env python3
"""[订单统计状态对齐 & 履约方式中文化 Bug 修复] 部署脚本
- 服务器拉取最新代码
- 重建并重启 backend / admin-web / h5-web 容器
- 在 backend 容器内运行新增的 pytest 测试
- 检查关键 URL 可达
"""
import io
import sys
import time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{PROJECT_ID}'
BASE_URL = f'https://{HOST}/autodev/{PROJECT_ID}'


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=600, stream=True):
    print(f"\n>>> {cmd}")
    sys.stdout.flush()
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', errors='replace')
            if stream:
                sys.stdout.write(data); sys.stdout.flush()
            out_buf.write(data)
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', errors='replace')
            if stream:
                sys.stdout.write(data); sys.stdout.flush()
            err_buf.write(data)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"[exit_code: {code}]")
    return out_buf.getvalue(), err_buf.getvalue(), code


def main():
    ssh = get_ssh()
    try:
        # 1. git 拉取最新代码
        run(ssh, f'cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline')

        # 2. 重建 backend（变更：product_admin.py + 新测试）
        run(ssh, f'cd {PROJECT_DIR} && docker compose build backend', timeout=900)
        run(ssh, f'cd {PROJECT_DIR} && docker compose up -d backend')

        # 3. 重建 admin-web（变更：statistics 页 + 多个履约方式映射）
        run(ssh, f'cd {PROJECT_DIR} && docker compose build admin-web', timeout=900)
        run(ssh, f'cd {PROJECT_DIR} && docker compose up -d admin-web')

        # 4. 重建 h5-web（变更：unified-order/[id] + products 页）
        run(ssh, f'cd {PROJECT_DIR} && docker compose build h5-web', timeout=900)
        run(ssh, f'cd {PROJECT_DIR} && docker compose up -d h5-web')

        # 5. 等待服务就绪
        print("\n等待服务就绪 30s ...")
        time.sleep(30)

        # 6. 容器状态
        run(ssh, f'docker ps --filter name={PROJECT_ID} --format "{{{{.Names}}}} {{{{.Status}}}}"')

        # 7. 在后端容器内运行新增的 pytest 测试
        backend_container = f'{PROJECT_ID}-backend'
        print("\n=== 运行新增的 pytest 测试 ===")
        run(ssh,
            f'docker exec {backend_container} python -m pytest '
            f'tests/test_orders_statistics_alignment.py '
            f'tests/test_fulfillment_label_dict.py '
            f'-v --tb=short 2>&1 | tail -150',
            timeout=600)

        # 8. 关键 URL 可达性检查（外部 80 端口）
        print("\n=== 外部 URL 可达性检查 ===")
        urls = [
            f'{BASE_URL}/',  # h5
            f'{BASE_URL}/admin',  # admin
            f'{BASE_URL}/api/admin/orders/statistics?start_at=2026-05-04&end_at=2026-05-04',  # 401/403 期望
            f'{BASE_URL}/api/admin/orders/v2/enums',
        ]
        for u in urls:
            run(ssh, f'curl -s -o /dev/null -w "{u} -> %{{http_code}}\\n" "{u}"', timeout=30)

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
