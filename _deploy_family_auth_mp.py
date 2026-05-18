"""[PRD-FAMILY-AUTH-MP-V1] 部署后端 invitation detail/accept 增强到测试服务器，
并重建/重启 backend 容器。"""
import os
import sys
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
PROJ = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{PROJ}'

FILES = [
    'backend/app/api/family_management.py',
    'backend/app/schemas/family_management.py',
    'backend/tests/test_family_auth_mp_v1.py',
]


def put(sftp, local, remote):
    rd = os.path.dirname(remote).replace('\\', '/')
    parts = rd.strip('/').split('/')
    cur = ''
    for p in parts:
        cur = f'{cur}/{p}'
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass
    sftp.put(local, remote)


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PWD, timeout=30)
    try:
        sftp = c.open_sftp()
        try:
            for rel in FILES:
                local = os.path.join(os.path.dirname(__file__), rel.replace('/', os.sep))
                if not os.path.exists(local):
                    print(f'[skip-missing] {rel}')
                    continue
                remote = f'{REMOTE_ROOT}/{rel}'
                put(sftp, local, remote)
                print(f'[uploaded] {rel}')
        finally:
            sftp.close()

        # 把变更同步进 backend 容器并重启服务（无需重建镜像，节省时间）
        print('[copy] copy backend src into running container')
        for rel in FILES:
            if not rel.startswith('backend/'):
                continue
            container_path = rel[len('backend/'):]  # app/...
            cmd = (
                f'docker cp {REMOTE_ROOT}/{rel} '
                f'{PROJ}-backend:/app/{container_path}'
            )
            _, out, _ = c.exec_command(cmd, timeout=60)
            rc = out.channel.recv_exit_status()
            print(f'  docker cp {rel}: rc={rc}')

        print('[restart] docker restart backend')
        _, out, _ = c.exec_command(f'docker restart {PROJ}-backend', timeout=120)
        rc = out.channel.recv_exit_status()
        print(f'rc={rc} | {out.read().decode().strip()[:500]}')

        # 等待健康
        print('[wait] sleep 8s for service to come up')
        import time
        time.sleep(8)

        print('[smoke] curl backend health')
        _, out, _ = c.exec_command(
            f'curl -sk -o /dev/null -w "%{{http_code}}" '
            f'https://{HOST}/autodev/{PROJ}/api/openapi.json',
            timeout=30,
        )
        code = out.read().decode().strip()
        print(f'openapi -> http {code}')
        if code != '200':
            print('[ERROR] backend not healthy')
            sys.exit(2)
    finally:
        c.close()


if __name__ == '__main__':
    main()
