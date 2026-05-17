"""[BUG_FIX_TIMEZONE_GLOBAL_20260517] 打包小程序 zip 并上传到测试服务器"""
import os
import secrets
import time
import zipfile

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
# 经验：之前打包脚本是把 zip 直接放到项目部署根目录下静态文件目录
# 实测 base URL 是 https://newbb.test.bangbangvip.com/autodev/<id>/，对应服务器路径需要找到
# 旧脚本里用过 /var/www/autodev/<id>/  和  /home/ubuntu/.../miniprogram/。
# 这里两个候选目录都试一下，谁存在用谁。
CANDIDATES = [
    f'/var/www/autodev/{PROJECT_ID}',
    f'/home/ubuntu/autodev/{PROJECT_ID}',
    f'/home/ubuntu/{PROJECT_ID}',
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)


def _run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.channel.recv_exit_status(), stdout.read().decode(), stderr.read().decode()


remote_dir = None
for d in CANDIDATES:
    c, _, _ = _run(f'test -d {d} && echo OK')
    if c == 0:
        remote_dir = d
        print(f'[remote_dir] found {d}')
        break

if not remote_dir:
    print('[err] 没找到部署目录，回退到 /home/ubuntu/autodev/<id>')
    remote_dir = f'/home/ubuntu/autodev/{PROJECT_ID}'
    _run(f'mkdir -p {remote_dir}')

REMOTE_PATH = f'{remote_dir}/{ZIP_NAME}'

sftp = ssh.open_sftp()
sftp.put(ZIP_LOCAL, REMOTE_PATH)
sftp.close()
_, out, _ = _run(f'ls -la {REMOTE_PATH}')
print(out)

# 验证 URL 是否可达
URL = f'https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/{ZIP_NAME}'
print(f'[upload] {URL}')

# 用 python 测一下
import urllib.request
try:
    req = urllib.request.Request(URL, method='HEAD')
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(f'[verify] HTTP {resp.status} {resp.headers.get("Content-Length", "?")} bytes')
except Exception as e:
    print(f'[verify FAIL] {e}')

ssh.close()
print(f'[DONE] {URL}')
