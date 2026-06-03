"""
[BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 部署脚本
将本次修改的前端文件上传到远程服务器并触发 H5/admin 容器内的代码热生效。
"""
import paramiko, os, sys, time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'

FILES = [
    'h5-web/src/lib/datetime.ts',
    'h5-web/src/app/health-metric/[type]/page.tsx',
    'h5-web/src/lib/__tests__/run_bp_format_test.mjs',
    'h5-web/src/lib/__tests__/run_datetime_bj_test.mjs',
    'admin-web/src/lib/datetime.ts',
    'miniprogram/utils/datetime.js',
    'flutter_app/lib/utils/datetime_utils.dart',
]

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    for rel in FILES:
        local = os.path.join(os.getcwd(), rel.replace('/', os.sep))
        if not os.path.exists(local):
            print(f'! local missing: {local}')
            continue
        remote = f'{REMOTE_ROOT}/{rel}'
        # 确保远程目录存在
        parts = remote.rsplit('/', 1)
        try:
            sftp.stat(parts[0])
        except IOError:
            stdin, stdout, stderr = c.exec_command(f'mkdir -p {parts[0]}')
            stdout.channel.recv_exit_status()
        sftp.put(local, remote)
        print(f'OK upload {rel}')
    sftp.close()

    # 在远端确认文件
    stdin, stdout, stderr = c.exec_command(
        f'cd {REMOTE_ROOT} && head -3 h5-web/src/lib/datetime.ts && echo "---" && '
        f'grep -c "BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530" h5-web/src/lib/datetime.ts admin-web/src/lib/datetime.ts miniprogram/utils/datetime.js flutter_app/lib/utils/datetime_utils.dart'
    )
    print(stdout.read().decode('utf-8', errors='replace'))

    # 触发 H5 与 admin-web 容器内重新构建（next build），不需要重建镜像
    print('=== rebuild h5-web container (next build) ===')
    cmd = (
        f'cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -20'
    )
    stdin, stdout, stderr = c.exec_command(cmd, timeout=900)
    out = stdout.read().decode('utf-8', errors='replace')
    print(out[-3000:])

    print('=== rebuild admin-web container ===')
    cmd = (
        f'cd {REMOTE_ROOT} && docker compose build admin-web 2>&1 | tail -20'
    )
    stdin, stdout, stderr = c.exec_command(cmd, timeout=900)
    out = stdout.read().decode('utf-8', errors='replace')
    print(out[-3000:])

    print('=== docker compose up -d h5-web admin-web ===')
    cmd = f'cd {REMOTE_ROOT} && docker compose up -d h5-web admin-web 2>&1 | tail -10'
    stdin, stdout, stderr = c.exec_command(cmd, timeout=180)
    print(stdout.read().decode('utf-8', errors='replace'))
    print(stderr.read().decode('utf-8', errors='replace'))

    c.close()

if __name__ == '__main__':
    main()
