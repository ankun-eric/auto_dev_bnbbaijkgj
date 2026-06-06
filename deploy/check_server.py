"""Check server state and save to file."""
import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

results = {}

stdin, stdout, stderr = ssh.exec_command('cat /home/ubuntu/gateway/nginx.conf', timeout=10)
results['nginx_conf'] = stdout.read().decode()

stdin, stdout, stderr = ssh.exec_command('ls -la /home/ubuntu/gateway/conf.d/', timeout=10)
results['confd'] = stdout.read().decode()

stdin, stdout, stderr = ssh.exec_command('ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ 2>&1', timeout=10)
results['proj_dir'] = stdout.read().decode()

stdin, stdout, stderr = ssh.exec_command('docker ps -a --filter name=6b099ed3 --format "{{.Names}} {{.Status}}" 2>&1', timeout=10)
results['containers'] = stdout.read().decode()

ssh.close()

with open('C:/auto_output/bnbbaijkgj/server_state.txt', 'w', encoding='utf-8') as f:
    for k, v in results.items():
        f.write(f'=== {k} ===\n{v}\n\n')
print('SAVED to server_state.txt')
