"""验证更多关键 H5 路径，含本次 Bug 涉及的 unified-order 页。"""
import sys, time, paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://{HOST}/autodev/{PROJECT_ID}'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

def run(cmd):
    chan = ssh.get_transport().open_session()
    chan.settimeout(60)
    chan.exec_command(cmd)
    out = []
    while True:
        if chan.recv_ready(): out.append(chan.recv(4096).decode('utf-8','replace'))
        if chan.recv_stderr_ready(): chan.recv_stderr(4096)
        if chan.exit_status_ready() and not chan.recv_ready(): break
        time.sleep(0.05)
    chan.recv_exit_status()
    return ''.join(out).strip()

urls = [
    f'{BASE_URL}/',
    f'{BASE_URL}/login',
    f'{BASE_URL}/home',
    f'{BASE_URL}/unified-orders',
    f'{BASE_URL}/unified-order/test-id-12345',
    f'{BASE_URL}/profile',
    f'{BASE_URL}/api/health',
]
print(f"{'STATUS':<8} URL")
print('-'*100)
for url in urls:
    code = run(f'curl -s -o /dev/null -w "%{{http_code}}" -L --max-time 15 "{url}"')
    print(f"{code:<8} {url}")

# 顺便验证 H5 页面真的包含本次新增的“拨打电话”逻辑（来自构建产物）
print('\n--- 容器日志末尾 ---')
print(run(f'docker logs --tail 25 {PROJECT_ID}-h5'))

print('\n--- 容器状态 ---')
print(run(f'docker ps --filter name={PROJECT_ID}-h5 --format "table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}"'))

ssh.close()
