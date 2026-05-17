"""打包小程序源码为 zip 并上传到测试服务器"""
import os, time, zipfile, paramiko

ROOT = os.path.dirname(os.path.abspath(__file__))
MP = os.path.join(ROOT, 'miniprogram')
STAMP = time.strftime('%Y%m%d_%H%M%S')
ZIP_NAME = f'miniprogram_{STAMP}_bug_report_interpret.zip'
ZIP_LOCAL = os.path.join(ROOT, ZIP_NAME)

EXCLUDE_DIRS = {'node_modules', '.git', 'unpackage', 'dist'}
EXCLUDE_EXTS = {'.log'}

with zipfile.ZipFile(ZIP_LOCAL, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(MP):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in EXCLUDE_EXTS:
                continue
            fp = os.path.join(root, f)
            arc = os.path.relpath(fp, MP)
            zf.write(fp, arc)

size_mb = os.path.getsize(ZIP_LOCAL) / 1024 / 1024
print(f'[zip] {ZIP_NAME}  {size_mb:.2f} MB')

REMOTE_DIR = '/var/www/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram'
REMOTE_PATH = f'{REMOTE_DIR}/{ZIP_NAME}'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
ssh.exec_command(f'mkdir -p {REMOTE_DIR}')[1].read()
sftp = ssh.open_sftp()
sftp.put(ZIP_LOCAL, REMOTE_PATH)
sftp.close()
stdin, stdout, stderr = ssh.exec_command(f'ls -la {REMOTE_PATH}')
print(stdout.read().decode())
ssh.close()
print(f'[uploaded] https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/{ZIP_NAME}')
