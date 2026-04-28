import zipfile
import os
import datetime
import random
import sys

# Generate unique filename
now = datetime.datetime.now()
rand_hex = '%04x' % random.randint(0, 0xFFFF)
filename = 'miniprogram_%s_%s.zip' % (now.strftime('%Y%m%d_%H%M%S'), rand_hex)
print('Filename: %s' % filename)

# Source directory
src_dir = r'C:\auto_output\bnbbaijkgj\miniprogram'
zip_path = os.path.join(r'C:\auto_output\bnbbaijkgj', filename)

# Exclusions
exclude_dirs = {'node_modules', '.git', '__pycache__', '.DS_Store'}

count = 0
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, os.path.dirname(src_dir))
            zf.write(file_path, arcname)
            count += 1

print('Zip created: %s' % zip_path)
print('Files included: %d' % count)
print('Size: %d bytes' % os.path.getsize(zip_path))

# Now upload via SSH
try:
    import paramiko
except ImportError:
    print('Installing paramiko...')
    os.system('pip install paramiko')
    import paramiko

server = 'newbb.test.bangbangvip.com'
user = 'ubuntu'
password = 'Newbang888'
remote_dir = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/'

print('\nConnecting to %s...' % server)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(server, username=user, password=password)

# Create remote directory
print('Creating remote directory: %s' % remote_dir)
stdin, stdout, stderr = ssh.exec_command('mkdir -p %s' % remote_dir)
stdout.channel.recv_exit_status()

# Upload file
print('Uploading %s...' % filename)
sftp = ssh.open_sftp()
remote_path = remote_dir + filename
sftp.put(zip_path, remote_path)
sftp.close()
print('Upload complete: %s' % remote_path)

# Check nginx config for static file serving
print('\nChecking nginx configuration...')
stdin, stdout, stderr = ssh.exec_command('docker exec gateway-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null || docker exec gateway-nginx cat /etc/nginx/nginx.conf 2>/dev/null')
nginx_conf = stdout.read().decode()
print('Nginx config length: %d' % len(nginx_conf))

# Check if there's already a location for the autodev static files
target_location = '/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/'
if target_location in nginx_conf or '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/' in nginx_conf:
    print('Static file location already configured in nginx.')
else:
    print('Need to add nginx location for static files.')
    # Check what nginx container config looks like
    stdin, stdout, stderr = ssh.exec_command('docker exec gateway-nginx ls /etc/nginx/conf.d/')
    conf_files = stdout.read().decode().strip()
    print('Nginx conf.d files: %s' % conf_files)
    
    # Find the main config file
    stdin, stdout, stderr = ssh.exec_command('docker exec gateway-nginx cat /etc/nginx/conf.d/default.conf')
    default_conf = stdout.read().decode()
    if not default_conf:
        stdin, stdout, stderr = ssh.exec_command('docker exec gateway-nginx ls /etc/nginx/conf.d/ && docker exec gateway-nginx cat /etc/nginx/conf.d/*.conf')
        default_conf = stdout.read().decode()
    
    print('\n--- Current nginx default.conf ---')
    print(default_conf[:2000])
    print('--- End ---')

# Test if file is accessible
print('\nTesting file accessibility...')
url = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/%s' % filename
stdin, stdout, stderr = ssh.exec_command('curl -sI "%s"' % url)
curl_result = stdout.read().decode()
print('Curl result:\n%s' % curl_result)

if '200' in curl_result:
    print('\nSUCCESS! File is accessible.')
else:
    print('\nFile not accessible yet. Need to fix nginx config.')
    print('NGINX_FIX_NEEDED')

ssh.close()

# Save filename for later use
with open(r'C:\auto_output\bnbbaijkgj\_upload_result.txt', 'w') as f:
    f.write(filename)

print('\n\nFinal URL: %s' % url)
