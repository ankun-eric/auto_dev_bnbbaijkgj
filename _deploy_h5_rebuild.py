"""把 h5-web 改动同步到远程仓库目录，并在服务器上重建 h5-web 镜像。"""
import os, paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
PROJ='6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT=f'/home/ubuntu/{PROJ}'

FILES = [
    'h5-web/src/app/(ai-chat)/ai-home/page.tsx',
]

def put(sftp, local, remote):
    rd = os.path.dirname(remote).replace('\\', '/')
    parts = rd.strip('/').split('/')
    cur = ''
    for p in parts:
        cur = f'{cur}/{p}'
        try: sftp.stat(cur)
        except IOError:
            try: sftp.mkdir(cur)
            except IOError: pass
    sftp.put(local, remote)

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,22,USER,PWD,timeout=30)
try:
    sftp = c.open_sftp()
    try:
        for rel in FILES:
            local = os.path.join(os.path.dirname(__file__), rel.replace('/', os.sep))
            remote = f'{REMOTE_ROOT}/{rel}'
            put(sftp, local, remote)
            print(f'[uploaded] {rel}')
    finally:
        sftp.close()
    # 重建 h5-web 镜像（不删除其他容器）
    print('[build] docker compose build h5-web ...')
    _, out, err = c.exec_command(
        f'cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -50',
        timeout=900,
    )
    rc = out.channel.recv_exit_status()
    print(f'rc={rc}\n{out.read().decode()[-4000:]}')
    print('[restart] docker compose up -d h5-web')
    _, out2, _ = c.exec_command(
        f'cd {REMOTE_ROOT} && docker compose up -d h5-web 2>&1',
        timeout=120,
    )
    print(out2.read().decode()[-2000:])
finally:
    c.close()
