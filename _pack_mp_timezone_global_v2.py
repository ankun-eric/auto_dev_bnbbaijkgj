"""[BUG_FIX_TIMEZONE_GLOBAL_20260517] 打包小程序 zip 并上传到 nginx 静态目录（路径已确认）"""
import os
import secrets
import time
import zipfile
import urllib.request

import paramiko

ROOT = os.path.dirname(os.path.abspath(__file__))
MP = os.path.join(ROOT, 'miniprogram')
STAMP = time.strftime('%Y%m%d_%H%M%S')
RAND = secrets.token_hex(2)
ZIP_NAME = f'miniprogram_{STAMP}_{RAND}_timezone_global.zip'
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

PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_DIR = f'/home/ubuntu/{PROJECT_ID}/static/miniprogram'
REMOTE_PATH = f'{REMOTE_DIR}/{ZIP_NAME}'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)


def _run(cmd, t=30):
    _, o, e = ssh.exec_command(cmd, timeout=t)
    return o.channel.recv_exit_status(), o.read().decode(), e.read().decode()


_run(f'mkdir -p {REMOTE_DIR}')
sftp = ssh.open_sftp()
sftp.put(ZIP_LOCAL, REMOTE_PATH)
sftp.close()
_, out, _ = _run(f'ls -la {REMOTE_PATH}')
print(out)
ssh.close()

URL = f'https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/miniprogram/{ZIP_NAME}'
print(f'[uploaded] {URL}')

# 验证
try:
    req = urllib.request.Request(URL, method='HEAD')
    with urllib.request.urlopen(req, timeout=20) as resp:
        size = resp.headers.get('Content-Length')
        print(f'[VERIFY OK] HTTP {resp.status}  size={size}')
        with open('_mp_zip_url.txt', 'w', encoding='utf-8') as f:
            f.write(URL)
except Exception as e:
    print(f'[VERIFY FAIL] {e}')
