"""端到端访问验证：API GET /api/health + 公开门店 contact + h5 首页可达。"""
import sys, time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE = f'https://{HOST}/autodev/{PROJECT_ID}'


def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=120, ignore_error=False):
    print(f'\n>>> {cmd}', flush=True)
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
    print(f'[exit_code: {code}]')
    return code


def main():
    ssh = get_ssh()
    try:
        # 1) API /api/health（GET，应当 200）
        run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}\\n" {BASE}/api/health')

        # 2) /api/orders/unified （需登录，应 401，证明走通了网关到 backend）
        run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}\\n" {BASE}/api/orders/unified')

        # 3) h5 首页（应 200/3xx）
        run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}\\n" {BASE}/')

        # 4) h5 订单详情（动态路由 placeholder，应 200，里面会动态拉数据）
        run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}\\n" {BASE}/unified-orders')

        # 5) 公开门店 contact 接口（任取 store_id=1，结构应当是 store_id/contact_phone 字段）
        run(ssh, f'curl -s {BASE}/api/stores/1/contact 2>&1 | head -c 500')
        print()

        # 6) 容器状态
        run(
            ssh,
            f'docker ps --format "{{{{.Names}}}}\\t{{{{.Status}}}}" | grep {PROJECT_ID}',
        )
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
