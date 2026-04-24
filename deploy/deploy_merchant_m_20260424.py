"""商家端移动端 H5 适配 部署脚本 (2026-04-24)

变更范围：
- h5-web: 新增 /merchant/m/* 独立移动端路由（antd-mobile），共 17 条
- h5-web: merchant/layout.tsx 新增移动端 UA 自动重定向
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd  # type: ignore

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'
C_H5 = f'{DEPLOY_ID}-h5'


def main() -> int:
    print('[deploy] connecting to server ...')
    ssh = create_client()
    try:
        # 1. git pull
        print('\n[deploy] git pull on server ...')
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'git fetch --all 2>&1 | Select-Object -Last 10; '
            f'git reset --hard origin/master 2>&1 | tail -10 && '
            f'git log -1 --oneline'
        )
        # 远程是 Linux，这里用 bash 形式
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'git fetch --all 2>&1 | tail -10 && '
            f'git reset --hard origin/master 2>&1 | tail -5 && '
            f'git log -1 --oneline'
        )
        out, err, code = run_cmd(ssh, cmd, timeout=180)
        print(out)
        if err:
            print('STDERR:', err)
        if code != 0:
            print(f'[deploy] git pull exit code: {code}')
            return code

        # 2. rebuild h5-web
        print('\n[deploy] rebuild h5-web container (may take ~3-5 min) ...')
        cmd = f'cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -50'
        out, err, code = run_cmd(ssh, cmd, timeout=1800)
        print(out)
        if code != 0:
            print(f'[deploy] h5-web build exit code: {code}')
            return code

        # 3. up -d h5-web
        print('\n[deploy] up -d h5-web ...')
        out, err, code = run_cmd(
            ssh,
            f'cd {REMOTE_ROOT} && docker compose up -d --no-deps h5-web 2>&1 | tail -10',
            timeout=180,
        )
        print(out)

        # 4. wait and check
        print('\n[deploy] sleep 15s then check containers ...')
        time.sleep(15)
        out, _, _ = run_cmd(
            ssh,
            f'docker ps --filter name={DEPLOY_ID}- --format "{{{{.Names}}}}\\t{{{{.Status}}}}"',
            timeout=60,
        )
        print(out)

        return 0
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
