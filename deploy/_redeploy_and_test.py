"""[2026-05-04 订单「联系商家」电话不显示 Bug 修复 v1.0]
重新部署 + 跑测试。Git fetch 超时，改用 SFTP 直接上传修复后的文件。
"""
import os
import sys
import time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{PROJECT_ID}'
BACKEND = f'{PROJECT_ID}-backend'
H5 = f'{PROJECT_ID}-h5'
GATEWAY = 'gateway'  # 真实容器名

LOCAL_ROOT = r'C:\auto_output\bnbbaijkgj'

# 需要直接上传到服务器并 docker cp 的文件（相对项目根）
FILES = [
    ('backend/app/schemas/unified_orders.py', f'{BACKEND}:/app/app/schemas/unified_orders.py'),
    ('backend/app/api/unified_orders.py', f'{BACKEND}:/app/app/api/unified_orders.py'),
    ('backend/app/api/stores_public.py', f'{BACKEND}:/app/app/api/stores_public.py'),
    ('backend/tests/test_contact_store_storeid_bugfix.py',
     f'{BACKEND}:/app/tests/test_contact_store_storeid_bugfix.py'),
]


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
    out_chunks = []
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_chunks.append(data)
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(4096).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_chunks.append(data)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"[exit_code: {code}]")
    if code != 0 and not ignore_error:
        print(f"FAIL: {cmd}")
    return code, ''.join(out_chunks)


def main():
    ssh = get_ssh()
    sftp = ssh.open_sftp()
    try:
        # 1) 上传修复后的文件到服务器项目目录
        for rel, dst in FILES:
            local_path = os.path.join(LOCAL_ROOT, rel.replace('/', os.sep))
            remote_path = f'{PROJECT_DIR}/{rel}'
            print(f'\n[upload] {local_path} -> {HOST}:{remote_path}')
            # 确保远端父目录存在
            run(ssh, f'mkdir -p $(dirname {remote_path})', ignore_error=True)
            sftp.put(local_path, remote_path)

        # 2) docker cp 进 backend 容器
        for rel, dst in FILES:
            run(ssh, f'docker cp {PROJECT_DIR}/{rel} {dst}')

        # 3) 重启 backend
        run(ssh, f'docker restart {BACKEND}', timeout=120)

        # 4) 等 backend 健康（用 python urllib 在容器里探活，因为容器没 curl）
        for i in range(20):
            code, _ = run(
                ssh,
                f"docker exec {BACKEND} python -c \"import urllib.request as u;"
                f"r=u.urlopen('http://localhost:8000/api/health',timeout=3);"
                f"print(r.status)\"",
                timeout=20,
                ignore_error=True,
            )
            if code == 0:
                print('OK backend healthy')
                break
            time.sleep(3)
        else:
            print('WARN backend health timeout')

        # 5) 跑回归测试
        run(
            ssh,
            f'docker exec {BACKEND} python -m pytest '
            f'tests/test_contact_store_storeid_bugfix.py '
            f'-v --tb=short -p no:cacheprovider 2>&1',
            timeout=300,
        )

        # 6) 端到端验证：调用 health
        run(
            ssh,
            f'curl -sI https://{HOST}/autodev/{PROJECT_ID}/api/health | head -3',
            ignore_error=True,
        )
        # 把 gateway 重连项目网络（h5 容器重建过）
        run(
            ssh,
            f'docker network connect {PROJECT_ID}-network {GATEWAY} 2>/dev/null || true',
            ignore_error=True,
        )
        run(ssh, f'docker exec {GATEWAY} nginx -s reload', ignore_error=True)
        # 再次访问验证
        run(
            ssh,
            f'curl -sI https://{HOST}/autodev/{PROJECT_ID}/api/health | head -3',
            ignore_error=True,
        )
        run(
            ssh,
            f'curl -sI https://{HOST}/autodev/{PROJECT_ID}/ | head -3',
            ignore_error=True,
        )
    finally:
        sftp.close()
        ssh.close()


if __name__ == '__main__':
    main()
