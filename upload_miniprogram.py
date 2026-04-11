import paramiko

project_id = '3b7b999d-e51c-4c0d-8f6e-baf90cd26857'
zip_name = 'miniprogram_20260408_114910_809c.zip'
backend_container = f'{project_id}-backend'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.bangbangvip.com', username='ubuntu', password='Newbang888')

# Check backend uploads directory
stdin, stdout, stderr = ssh.exec_command(f'docker exec {backend_container} ls /app/uploads/ 2>&1 | head -10')
print('Backend uploads:', stdout.read().decode())

# Copy zip to backend uploads
stdin, stdout, stderr = ssh.exec_command(f'docker cp /tmp/{zip_name} {backend_container}:/app/uploads/{zip_name} 2>&1')
out = stdout.read().decode()
err = stderr.read().decode()
print('docker cp to backend result:', out, err)

# Verify
stdin, stdout, stderr = ssh.exec_command(f'docker exec {backend_container} ls -la /app/uploads/{zip_name} 2>&1')
print('File in backend uploads:', stdout.read().decode())

# Test the uploads URL
stdin, stdout, stderr = ssh.exec_command(f'curl -Is "https://newbb.bangbangvip.com/autodev/{project_id}/uploads/{zip_name}" 2>&1 | head -5')
print('Uploads URL test:', stdout.read().decode())

ssh.close()
