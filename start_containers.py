import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

PROJ_DIR = '/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857'

print('=== Starting containers ===')
stdin, stdout, stderr = ssh.exec_command(
    'cd ' + PROJ_DIR + ' && docker compose -f docker-compose.prod.yml up -d 2>&1'
)
exit_status = stdout.channel.recv_exit_status()
print(stdout.read().decode())
print('Exit status:', exit_status)

# Wait for containers to be healthy
print('\nWaiting 15s for containers to start...')
time.sleep(15)

# Check container status
print('\n=== Container status ===')
stdin, stdout, stderr = ssh.exec_command(
    'cd ' + PROJ_DIR + ' && docker compose -f docker-compose.prod.yml ps 2>&1'
)
print(stdout.read().decode())

# Check logs for errors
print('\n=== Backend logs (last 30 lines) ===')
stdin, stdout, stderr = ssh.exec_command(
    'cd ' + PROJ_DIR + ' && docker compose -f docker-compose.prod.yml logs --tail=30 backend 2>&1'
)
print(stdout.read().decode())

ssh.close()
