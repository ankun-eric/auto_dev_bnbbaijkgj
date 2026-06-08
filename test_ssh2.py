import paramiko
import posixpath
import sys

sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)
print('connected', flush=True)

sftp = client.open_sftp()
api_dir = posixpath.join('/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend', 'app', 'api')
print('api_dir:', api_dir, flush=True)

try:
    items = sftp.listdir_attr(api_dir)
    for i in items:
        print(i.filename, flush=True)
except Exception as e:
    print('Error:', e, flush=True)

sftp.close()
client.close()
print('done', flush=True)
