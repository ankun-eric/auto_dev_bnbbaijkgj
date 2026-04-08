import paramiko
import os

zip_name = 'miniprogram_20260408_114910_809c.zip'
local_path = f'C:/auto_output/bnbbaijkgj/{zip_name}'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Bangbang987')

# Check H5 container's public directory
stdin, stdout, stderr = ssh.exec_command('docker exec 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-h5 ls /app/public/ 2>/dev/null | head -20')
print('H5 public dir:', stdout.read().decode())
print('err:', stderr.read().decode())

# Check if there are existing miniprogram zips in h5 public
stdin, stdout, stderr = ssh.exec_command('docker exec 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-h5 ls /app/public/ 2>/dev/null | grep miniprogram')
print('Existing miniprogram zips in h5:', stdout.read().decode())

# Check verify-miniprogram directory
stdin, stdout, stderr = ssh.exec_command('ls /home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/verify-miniprogram/')
print('verify-miniprogram dir:', stdout.read().decode())

ssh.close()
