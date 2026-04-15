import paramiko
import os

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
REMOTE_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/'
LOCAL_DIR = r'C:\auto_output\bnbbaijkgj\_deploy_tmp'

files = [
    'miniprogram_20260415_003643_6966.zip',
    'verify_miniprogram_20260415_003646_7b16.zip',
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD)

sftp = ssh.open_sftp()

for f in files:
    local_path = os.path.join(LOCAL_DIR, f)
    remote_path = REMOTE_DIR + f
    size = os.path.getsize(local_path)
    print(f"Uploading {f} ({size} bytes) -> {remote_path}")
    sftp.put(local_path, remote_path)
    remote_stat = sftp.stat(remote_path)
    print(f"  Uploaded OK, remote size: {remote_stat.st_size} bytes")

sftp.close()

print("\nVerifying files on server...")
stdin, stdout, stderr = ssh.exec_command(f'ls -la {REMOTE_DIR}')
print(stdout.read().decode())

ssh.close()
print("Done!")
