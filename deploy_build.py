import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Bangbang987', timeout=30)

PROJ_DIR = '/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857'

# Start build in background
print('Starting build in background on server...')
cmd = 'cd ' + PROJ_DIR + ' && nohup docker compose -f docker-compose.prod.yml build --no-cache > /tmp/build_output.log 2>&1 &'
stdin, stdout, stderr = ssh.exec_command(cmd)
stdout.channel.recv_exit_status()
print('Build started')

time.sleep(5)
stdin, stdout, stderr = ssh.exec_command('ps aux | grep compose | grep -v grep')
print('Build processes:', stdout.read().decode())

ssh.close()
