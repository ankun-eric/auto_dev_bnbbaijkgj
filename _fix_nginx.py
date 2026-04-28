import paramiko

server = 'newbb.test.bangbangvip.com'
user = 'ubuntu'
password = 'Newbang888'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(server, username=user, password=password)

# Find gateway-nginx container and its config
print('=== Finding nginx container ===')
stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}" | grep -i nginx')
containers = stdout.read().decode().strip()
print('Nginx containers: %s' % containers)

# Check the nginx container's config mount
print('\n=== Checking nginx config locations ===')
for container in containers.split('\n'):
    if not container.strip():
        continue
    print('\nContainer: %s' % container)
    stdin, stdout, stderr = ssh.exec_command('docker inspect %s --format "{{json .Mounts}}"' % container)
    mounts = stdout.read().decode()
    print('Mounts: %s' % mounts[:2000])
    
    stdin, stdout, stderr = ssh.exec_command('docker exec %s ls /etc/nginx/conf.d/' % container)
    print('conf.d contents: %s' % stdout.read().decode().strip())
    
    stdin, stdout, stderr = ssh.exec_command('docker exec %s cat /etc/nginx/conf.d/default.conf 2>/dev/null' % container)
    conf = stdout.read().decode()
    if conf:
        print('default.conf:\n%s' % conf[:3000])
    
    stdin, stdout, stderr = ssh.exec_command('docker exec %s cat /etc/nginx/nginx.conf' % container)
    nginx_main = stdout.read().decode()
    print('\nnginx.conf:\n%s' % nginx_main[:3000])

# Check if there's a docker-compose or config file on the host
print('\n=== Checking host nginx config files ===')
stdin, stdout, stderr = ssh.exec_command('find /home/ubuntu -name "nginx*" -o -name "*.conf" 2>/dev/null | head -30')
print(stdout.read().decode())

stdin, stdout, stderr = ssh.exec_command('find /home/ubuntu -name "docker-compose*" 2>/dev/null | head -10')
print('Docker compose files: %s' % stdout.read().decode())

# Check the autodev path mapping
print('\n=== Checking existing autodev routing ===')
stdin, stdout, stderr = ssh.exec_command('docker exec gateway-nginx grep -r "autodev" /etc/nginx/ 2>/dev/null')
print('autodev in nginx: %s' % stdout.read().decode())

stdin, stdout, stderr = ssh.exec_command('docker exec gateway-nginx grep -r "6b099ed3" /etc/nginx/ 2>/dev/null')
print('6b099ed3 in nginx: %s' % stdout.read().decode())

ssh.close()
