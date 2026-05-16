"""打包小程序 zip + 上传到服务器。"""
import os, zipfile, time, random, string, paramiko
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parent
MP_DIR = PROJ_ROOT / 'miniprogram'

HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
PROJ_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT=f'/home/ubuntu/{PROJ_ID}'

ts = time.strftime('%Y%m%d_%H%M%S')
rnd = ''.join(random.choices(string.hexdigits.lower(), k=4))
zip_name = f'miniprogram_bug_report_interpret_{ts}_{rnd}.zip'
zip_path = PROJ_ROOT / zip_name

print(f'[pack] zipping {MP_DIR} -> {zip_path}')
EXCLUDE_DIR = {'.git', 'node_modules', '__pycache__'}

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(MP_DIR):
        # 过滤
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR]
        for f in files:
            full = Path(root) / f
            arcname = full.relative_to(MP_DIR.parent)  # 包含 miniprogram/...
            zf.write(full, arcname)

print(f'[pack] size={zip_path.stat().st_size} bytes')

# 上传到 backend 的 /app/uploads 静态目录（自动暴露到 {base_url}/uploads/...）
# 但实际部署里更稳的是上传到 h5 公共 public 目录或直接放到 backend uploads
# 我们传到 backend uploads/static/
REMOTE_DEST = f'/home/ubuntu/{PROJ_ID}_static/{zip_name}'
print(f'[ssh] uploading to {REMOTE_DEST}')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,22,USER,PWD,timeout=30)
try:
    # 先在 nginx 暴露的目录下放
    _, _, _ = c.exec_command(f'mkdir -p /home/ubuntu/{PROJ_ID}_static')
    sftp = c.open_sftp()
    try:
        sftp.put(str(zip_path), REMOTE_DEST)
    finally:
        sftp.close()
    # 拷到 backend 容器的 uploads（这是通过 nginx /uploads 提供下载的常见位置）
    _, o, e = c.exec_command(
        f'docker cp {REMOTE_DEST} {PROJ_ID}-backend:/app/uploads/{zip_name}'
    )
    print('docker cp:', o.read().decode(), e.read().decode())
finally:
    c.close()

# 验证下载
import requests
url = f'https://newbb.test.bangbangvip.com/autodev/{PROJ_ID}/uploads/{zip_name}'
print(f'[verify] HEAD {url}')
r = requests.head(url, timeout=20, allow_redirects=True)
print(f'  HTTP {r.status_code} {r.headers.get("Content-Length")}')
print(f'\nDOWNLOAD_URL={url}')
