"""检查服务器上 H5 项目目录与 docker-compose 现状"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

cmds = [
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ | head -30',
    'docker ps --filter name=6b099ed3 --format "{{.Names}}|{{.Image}}|{{.Status}}"',
    'cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.yml 2>/dev/null | head -120',
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/ 2>/dev/null | head -10',
    'ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/src 2>/dev/null | head -10',
    'cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/Dockerfile 2>/dev/null | head -50',
]
for c in cmds:
    print('=' * 70)
    print('$', c)
    print('=' * 70)
    _, out, err = ssh.exec_command(c, timeout=30)
    print(out.read().decode(errors='replace'))
    e = err.read().decode(errors='replace')
    if e:
        print('ERR:', e)
ssh.close()
