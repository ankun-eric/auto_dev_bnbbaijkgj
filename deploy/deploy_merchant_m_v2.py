"""商家端移动端 H5 适配 部署脚本 v2 (2026-04-24)

策略：
1. 通过 SCP 上传 h5-web/src/app/merchant/m 整个目录
2. 上传修改后的 h5-web/src/app/merchant/layout.tsx
3. 远程 rebuild h5-web 容器
"""
from __future__ import annotations

import os
import sys
import time
import paramiko

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd  # type: ignore

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'
C_H5 = f'{DEPLOY_ID}-h5'

LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # C:\auto_output\bnbbaijkgj


def upload_dir(sftp: paramiko.SFTPClient, local_dir: str, remote_dir: str) -> int:
    """递归上传本地目录到远程，返回上传文件数"""
    count = 0
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass
    for name in os.listdir(local_dir):
        lp = os.path.join(local_dir, name)
        rp = f'{remote_dir}/{name}'
        if os.path.isdir(lp):
            count += upload_dir(sftp, lp, rp)
        else:
            sftp.put(lp, rp)
            count += 1
    return count


def main() -> int:
    print('[deploy] connecting to server ...')
    ssh = create_client()
    try:
        sftp = ssh.open_sftp()

        # 1. 上传 /merchant/m/ 整个目录
        local_m = os.path.join(LOCAL_ROOT, 'h5-web', 'src', 'app', 'merchant', 'm')
        remote_m = f'{REMOTE_ROOT}/h5-web/src/app/merchant/m'
        print(f'\n[deploy] uploading {local_m} -> {remote_m}')
        # 先确保父目录存在
        run_cmd(ssh, f'mkdir -p {remote_m}', timeout=10)
        # 清空旧目录（如果上一次部署有，防止陈旧文件）
        run_cmd(ssh, f'rm -rf {remote_m}', timeout=10)
        n = upload_dir(sftp, local_m, remote_m)
        print(f'[deploy] uploaded {n} files under /merchant/m/')

        # 2. 上传修改后的 layout.tsx
        local_layout = os.path.join(LOCAL_ROOT, 'h5-web', 'src', 'app', 'merchant', 'layout.tsx')
        remote_layout = f'{REMOTE_ROOT}/h5-web/src/app/merchant/layout.tsx'
        print(f'\n[deploy] uploading layout.tsx')
        sftp.put(local_layout, remote_layout)

        sftp.close()

        # 3. 校验文件已同步
        out, _, _ = run_cmd(ssh, f'ls {remote_m}', timeout=10)
        print('[deploy] /merchant/m/ contents:')
        print(out)

        # 4. rebuild h5-web
        print('\n[deploy] docker compose build h5-web (may take 3-6 min) ...')
        cmd = f'cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -60'
        out, err, code = run_cmd(ssh, cmd, timeout=1800)
        print(out)
        if code != 0:
            print(f'[deploy] h5-web build exit code: {code}')
            if err:
                print('STDERR:', err)
            return code

        # 5. up -d
        print('\n[deploy] up -d h5-web ...')
        out, err, code = run_cmd(
            ssh,
            f'cd {REMOTE_ROOT} && docker compose up -d --no-deps h5-web 2>&1 | tail -10',
            timeout=180,
        )
        print(out)

        # 6. wait
        print('\n[deploy] sleep 12s then check containers ...')
        time.sleep(12)
        out, _, _ = run_cmd(
            ssh,
            f'docker ps --filter name={DEPLOY_ID}- --format "{{{{.Names}}}}\\t{{{{.Status}}}}"',
            timeout=30,
        )
        print(out)

        # 7. simple health check
        print('\n[deploy] simple container log check ...')
        out, _, _ = run_cmd(ssh, f'docker logs --tail 20 {C_H5} 2>&1', timeout=30)
        print(out)

        return 0
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
