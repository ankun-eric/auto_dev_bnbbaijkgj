import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

PROJ_DIR = '/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857'

print('Waiting for build to complete...')
max_wait = 600  # 10 minutes
elapsed = 0
interval = 30

while elapsed < max_wait:
    # Check if build process is still running
    stdin, stdout, stderr = ssh.exec_command('ps aux | grep "docker-buildx bake" | grep -v grep | wc -l')
    count = stdout.read().decode().strip()
    
    # Check last lines of build log
    stdin, stdout, stderr = ssh.exec_command('tail -5 /tmp/build_output.log 2>/dev/null || echo "no log yet"')
    log_tail = stdout.read().decode().strip()
    
    print(f'[{elapsed}s] Build processes: {count}, Log tail: {log_tail[:200]}')
    
    if count == '0':
        print('Build process finished!')
        break
    
    time.sleep(interval)
    elapsed += interval

# Show final build log
print('\n=== Final build log (last 50 lines) ===')
stdin, stdout, stderr = ssh.exec_command('tail -50 /tmp/build_output.log 2>/dev/null')
print(stdout.read().decode())

ssh.close()
