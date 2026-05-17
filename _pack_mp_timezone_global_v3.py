"""[BUG_FIX_TIMEZONE_GLOBAL_V3_20260517] v3 全系统时区根治 - 小程序打包上传脚本

流程：
1. 把 miniprogram/ 目录打包成 zip（排除 node_modules/.git/__pycache__/.DS_Store）
2. 上传到服务器 nginx 静态目录 + h5-web 容器 /app/public/
3. 验证下载 URL HTTP 200
"""
from __future__ import annotations

import os
import secrets
import time
import zipfile
import urllib.request

import paramiko

ROOT = os.path.dirname(os.path.abspath(__file__))
MP = os.path.join(ROOT, 'miniprogram')
HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://{HOST}/autodev/{PROJECT_ID}'

STAMP = time.strftime('%Y%m%d_%H%M%S')
RAND = secrets.token_hex(2)
ZIP_NAME = f'miniprogram_{STAMP}_{RAND}.zip'
ZIP_LOCAL = os.path.join(ROOT, ZIP_NAME)

EXCLUDE_DIRS = {'node_modules', '.git', '__pycache__', 'unpackage', 'dist'}
EXCLUDE_FILES = {'.DS_Store'}
EXCLUDE_EXTS = {'.log'}


def pack_zip() -> None:
    n = 0
    with zipfile.ZipFile(ZIP_LOCAL, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                fp = os.path.join(root, f)
                arc = os.path.relpath(fp, MP)
                zf.write(fp, arc)
                n += 1
    size_mb = os.path.getsize(ZIP_LOCAL) / 1024 / 1024
    print(f'[zip] {ZIP_NAME}  files={n}  size={size_mb:.2f} MB')


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    return cli


def run(cli, cmd, t=60):
    _, o, e = cli.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    return code, o.read().decode('utf-8', 'replace'), e.read().decode('utf-8', 'replace')


def find_remote_dir(cli) -> str:
    for d in (
        f'/home/ubuntu/autodev/{PROJECT_ID}',
        f'/home/ubuntu/{PROJECT_ID}',
        f'/root/autodev/{PROJECT_ID}',
    ):
        c, _, _ = run(cli, f'test -d {d}')
        if c == 0:
            return d
    return f'/home/ubuntu/{PROJECT_ID}'


def upload_and_deploy() -> str:
    cli = ssh_connect()
    try:
        remote_proj = find_remote_dir(cli)
        print(f'[remote_proj] {remote_proj}')

        host_static_dir = f'{remote_proj}/static/miniprogram'
        host_static_path = f'{host_static_dir}/{ZIP_NAME}'
        host_pub_dir = f'{remote_proj}/h5-web/public'
        host_pub_path = f'{host_pub_dir}/{ZIP_NAME}'

        run(cli, f'mkdir -p {host_static_dir}')
        run(cli, f'mkdir -p {host_pub_dir}')

        sftp = cli.open_sftp()
        print('[sftp] uploading to host static dir...')
        sftp.put(ZIP_LOCAL, host_static_path)
        print(f'[sftp] uploaded {host_static_path}')
        print('[sftp] uploading to host h5-web/public ...')
        sftp.put(ZIP_LOCAL, host_pub_path)
        print(f'[sftp] uploaded {host_pub_path}')
        sftp.close()

        c, out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -i h5")
        h5_container = ''
        for line in out.splitlines():
            line = line.strip()
            if line and PROJECT_ID[:8] in line or 'h5' in line.lower():
                h5_container = line
                break
        if not h5_container:
            c, out, _ = run(cli, "docker ps --format '{{.Names}}'")
            print(f'[docker ps]\n{out}')
        else:
            print(f'[h5_container] {h5_container}')
            cp_cmd = f'docker cp {host_pub_path} {h5_container}:/app/public/{ZIP_NAME}'
            c, o2, e2 = run(cli, cp_cmd)
            print(f'[docker cp] code={c} {o2}{e2}')

        c, out, _ = run(cli, f'ls -la {host_static_path} {host_pub_path} 2>&1')
        print(out)
        return h5_container
    finally:
        cli.close()


def verify(url: str) -> int:
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=20) as resp:
            size = resp.headers.get('Content-Length')
            print(f'[VERIFY] HTTP {resp.status}  size={size}  url={url}')
            return resp.status
    except urllib.error.HTTPError as e:
        print(f'[VERIFY FAIL] HTTP {e.code} url={url}')
        return e.code
    except Exception as e:
        print(f'[VERIFY ERR] {e}  url={url}')
        return 0


def check_nginx(cli=None):
    own = cli is None
    if own:
        cli = ssh_connect()
    try:
        c, out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -iE 'gateway|nginx'")
        print(f'[gateway containers]\n{out}')
        for name in out.splitlines():
            name = name.strip()
            if not name:
                continue
            c2, out2, _ = run(cli, f"docker exec {name} sh -c 'cat /etc/nginx/conf.d/*.conf 2>/dev/null | grep -A 30 \"{PROJECT_ID[:8]}\"'")
            if out2.strip():
                print(f'[{name} conf snippet]\n{out2}')
                return name, out2
    finally:
        if own:
            cli.close()
    return '', ''


def main() -> None:
    pack_zip()
    upload_and_deploy()

    candidate_urls = [
        f'{BASE_URL}/miniprogram/{ZIP_NAME}',
        f'{BASE_URL}/{ZIP_NAME}',
    ]

    final_url = ''
    final_status = 0
    for u in candidate_urls:
        s = verify(u)
        if s == 200:
            final_url = u
            final_status = s
            break

    if final_status != 200:
        print('[!!] none of the candidate URLs returned 200, dumping nginx config...')
        cli = ssh_connect()
        try:
            check_nginx(cli)
            c, out, _ = run(cli, f"docker exec $(docker ps --format '{{{{.Names}}}}' | grep -iE 'gateway|nginx' | head -n1) sh -c 'grep -rn \"{PROJECT_ID}\" /etc/nginx/ 2>/dev/null | head -n 50'")
            print(f'[nginx grep]\n{out}')
        finally:
            cli.close()
        for u in candidate_urls:
            s = verify(u)
            if s == 200:
                final_url = u
                final_status = s
                break

    print('=' * 60)
    print(f'ZIP_NAME: {ZIP_NAME}')
    print(f'FINAL_URL: {final_url or candidate_urls[0]}')
    print(f'HTTP: {final_status}')
    print('=' * 60)

    if final_url:
        with open(os.path.join(ROOT, '_mp_zip_url.txt'), 'w', encoding='utf-8') as f:
            f.write(final_url)


if __name__ == '__main__':
    main()
