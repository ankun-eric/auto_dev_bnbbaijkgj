"""把后端改动文件 docker cp 进容器并重启。"""
import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
CTR='6b099ed3-7175-4a78-91f4-44570c84ed27-backend'
PROJ='6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT=f'/home/ubuntu/{PROJ}'

FILES = [
    ('backend/app/api/chat.py',                                        '/app/app/api/chat.py'),
    ('backend/app/schemas/chat.py',                                    '/app/app/schemas/chat.py'),
    ('backend/app/services/report_interpret_engine.py',                '/app/app/services/report_interpret_engine.py'),
    ('backend/app/services/family_self_backfill_migration.py',         '/app/app/services/family_self_backfill_migration.py'),
    ('backend/app/main.py',                                            '/app/app/main.py'),
]

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,22,USER,PWD,timeout=30)
try:
    for rel, inside in FILES:
        host_path = f'{REMOTE_ROOT}/{rel}'
        cmd = f'docker cp {host_path} {CTR}:{inside}'
        _, out, err = c.exec_command(cmd, timeout=60)
        rc = out.channel.recv_exit_status()
        print(f'[cp] {rel} -> {inside}  rc={rc} err={err.read().decode()[:200]}')
    # 删除 pyc 缓存（防止 main.py 改了但模块缓存）
    _, out, _ = c.exec_command(
        f"docker exec {CTR} sh -c 'find /app/app -name __pycache__ -type d | xargs -r rm -rf'",
        timeout=30,
    )
    print('[clean pyc]', out.read().decode()[:200])
    # 重启
    _, out, err = c.exec_command(f'docker restart {CTR}', timeout=120)
    print('[restart]', out.read().decode().strip(), err.read().decode().strip())
finally:
    c.close()
