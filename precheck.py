import paramiko
import os

os.chdir(r'C:\auto_output\bnbbaijkgj')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print('Connecting...')
ssh.connect('134.175.97.26', port=22, username='ubuntu', password='Newbang888', timeout=20, banner_timeout=20)
print('Connected!')

# Pre-check 1
stdin, stdout, stderr = ssh.exec_command('cat /home/ubuntu/gateway/nginx.conf', timeout=15)
with open('precheck_1.txt', 'w', encoding='utf-8') as f:
    f.write(stdout.read().decode())
print('Pre-check 1 done')

# Pre-check 2
stdin, stdout, stderr = ssh.exec_command('grep -rn "location\\|server_name" /home/ubuntu/gateway/conf.d/ 2>/dev/null; echo "===MAIN==="; grep -n "location\\|server_name\\|include" /home/ubuntu/gateway/nginx.conf 2>/dev/null', timeout=15)
with open('precheck_2.txt', 'w', encoding='utf-8') as f:
    f.write(stdout.read().decode())
print('Pre-check 2 done')

# Pre-check 4
stdin, stdout, stderr = ssh.exec_command('docker ps -a --filter name=gateway-nginx --format "{{.Names}} {{.Status}}"; echo "---"; docker network ls --filter name=6b099ed3-7175-4a78-91f4-44570c84ed27-network --format "{{.Name}}"; echo "---"; docker ps --format "{{.Names}} {{.Status}}"', timeout=15)
with open('precheck_4.txt', 'w', encoding='utf-8') as f:
    f.write(stdout.read().decode())
print('Pre-check 4 done')

# Pre-check 6
stdin, stdout, stderr = ssh.exec_command('df -h / | tail -1; echo "---"; docker system df 2>/dev/null | head -10', timeout=15)
with open('precheck_6.txt', 'w', encoding='utf-8') as f:
    f.write(stdout.read().decode())
print('Pre-check 6 done')

ssh.close()
print('ALL DONE')
