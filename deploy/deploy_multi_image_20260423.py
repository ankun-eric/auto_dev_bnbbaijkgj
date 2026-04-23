"""Deploy multi-image fix (2026-04-23) to server via SFTP.

Changes:
- backend/app/models/models.py          (add file_urls/thumbnail_urls/original_image_urls fields)
- backend/app/services/report_interpret_migration.py   (DDL + data backfill)
- backend/app/api/ocr.py                (write multi-urls)
- backend/app/api/report_interpret.py   (read prefer file_urls, fallback file_url)
- backend/app/api/chat.py               (reports_brief returns file_urls/thumbnail_urls)
- h5-web/src/app/checkup/chat/[sessionId]/page.tsx  (multi-image viewer)
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

FILES = [
    ('backend/app/models/models.py', 'backend/app/models/models.py'),
    ('backend/app/services/report_interpret_migration.py',
     'backend/app/services/report_interpret_migration.py'),
    ('backend/app/api/ocr.py', 'backend/app/api/ocr.py'),
    ('backend/app/api/report_interpret.py', 'backend/app/api/report_interpret.py'),
    ('backend/app/api/chat.py', 'backend/app/api/chat.py'),
    ('h5-web/src/app/checkup/chat/[sessionId]/page.tsx',
     'h5-web/src/app/checkup/chat/[sessionId]/page.tsx'),
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
            sftp.put(local_path, remote_path)

        sftp.close()

        # 重启后端容器（后端改动 + migration 会自动执行）
        print('[deploy] restart backend container ...')
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'docker compose restart backend 2>&1 | tail -20'
        )
        out, err, code = run_cmd(ssh, cmd, timeout=180)
        print(out)
        if err:
            print('STDERR:', err)

        # 重构前端 h5-web
        print('[deploy] rebuild h5-web container ...')
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

        # 等待容器启动
        print('[deploy] sleep 10s then check ...')
        time.sleep(10)
        out, err, _ = run_cmd(ssh, f'docker ps --filter name={DEPLOY_ID}- --format "{{{{.Names}}}}\\t{{{{.Status}}}}"', timeout=60)
        print(out)

        # 看 backend 启动日志确认迁移已执行
        print('[deploy] backend recent logs ...')
        out, err, _ = run_cmd(
            ssh,
            f'docker logs --tail 60 {DEPLOY_ID}-backend 2>&1 | grep -E "multi|migration|file_urls|ERROR" || true',
            timeout=30,
        )
        print(out)

        return 0
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
