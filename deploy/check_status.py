import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)
print('connected', flush=True)

cmds = [
    'hostname',
    'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git log --oneline -2',
    'docker ps -a --filter name=6b099ed3',
    'docker images 6b099ed3*',
]
for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f'\n>>> {cmd}')
    print(f'EXIT={exit_code}')
    if out: print(out)
    if err and exit_code != 0: print('ERR:', err)

ssh.close()
print('\ndone')
