"""Fix nginx.conf using sed -i (preserves inode)."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)

# Remove all lines containing our DEPLOY_ID from nginx.conf
i, o, e = c.exec_command("sed -i '/6b099ed3-7175-4a78-91f4-44570c84ed27/d' /home/ubuntu/gateway/nginx.conf")
o.read(); e.read()

# Verify
i, o, e = c.exec_command('docker exec gateway-nginx wc -l /etc/nginx/nginx.conf')
print('Container lines:', o.read().decode().strip())

i, o, e = c.exec_command('docker exec gateway-nginx grep 6b099ed3 /etc/nginx/nginx.conf || echo CLEAN')
print('Grep:', o.read().decode().strip())

# Test nginx
i, o, e = c.exec_command('docker exec gateway-nginx nginx -t 2>&1')
out = o.read().decode()
err = e.read().decode()
combined = out + err
if 'successful' in combined.lower():
    print('Nginx test: SUCCESS')
    i, o, e = c.exec_command('docker exec gateway-nginx nginx -s reload 2>&1')
    print('Reload:', o.read().decode().strip())
else:
    print('Nginx test: FAILED')
    for line in combined.split('\n'):
        if ('emerg' in line or 'error' in line) and 'deprecated' not in line:
            print('  ', line.strip())

c.close()
