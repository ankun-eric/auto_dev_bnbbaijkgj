"""Deploy UI polish PRD (2026-04-23) to server via SFTP.

Only three H5 files need to be synced. Then rebuild h5 container.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd  # type: ignore

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'
LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# (local_rel, remote_rel)
FILES = [
    ('h5-web/src/app/(tabs)/ai/page.tsx', 'h5-web/src/app/(tabs)/ai/page.tsx'),
    ('h5-web/src/components/ChatSidebar.tsx', 'h5-web/src/components/ChatSidebar.tsx'),
    ('h5-web/src/app/my-addresses/page.tsx', 'h5-web/src/app/my-addresses/page.tsx'),
]


def main() -> int:
    print('[deploy] connecting to server ...')
    ssh = create_client()
    sftp = ssh.open_sftp()

    try:
        for local_rel, remote_rel in FILES:
            local_path = os.path.join(LOCAL_ROOT, local_rel.replace('/', os.sep))
            remote_path = f'{REMOTE_ROOT}/{remote_rel}'
            if not os.path.isfile(local_path):
                print(f'[deploy] ERROR local not found: {local_path}')
                return 1
            print(f'[deploy] upload {local_rel} -> {remote_path}')
            # ensure remote dir exists (should already)
            sftp.put(local_path, remote_path)

        sftp.close()

        print('[deploy] rebuild h5 container ...')
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'docker compose build h5-web 2>&1 | tail -40 && '
            f'docker compose up -d --no-deps h5-web 2>&1 | tail -20'
        )
        out, err, code = run_cmd(ssh, cmd, timeout=1200)
        print(out)
        if err:
            print('STDERR:', err)
        if code != 0:
            print(f'[deploy] rebuild exit code: {code}')
            return code

        # wait and health check
        print('[deploy] sleep 8s then status ...')
        time.sleep(8)
        out, err, code = run_cmd(ssh, f'docker ps --filter name={DEPLOY_ID}-h5 --format "{{{{.Names}}}}\\t{{{{.Status}}}}"', timeout=60)
        print(out)

        return 0
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
