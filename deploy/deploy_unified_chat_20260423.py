"""Deploy 2026-04-23 Phase 2 (multi-image + unified chat page) to server via SFTP.

Changes (backend + h5-web + admin-web only; miniprogram/flutter are packaged separately):
- backend/app/api/chat.py                            (session detail adds type/interpret_session_id/compare_report_ids/auto_start_supported)
- backend/scripts/migrate_checkup_multi_image.py     (new standalone backfill script)
- backend/tests/test_multi_image_session_fields.py   (new tests)
- h5-web/src/app/chat/[sessionId]/page.tsx           (unified chat page, report cards, auto_start, SSE)
- h5-web/src/app/checkup/chat/[sessionId]/page.tsx   (deprecation note, kept as fallback)
- h5-web/src/app/checkup/compare/select/page.tsx     (redirect to /chat/)
- h5-web/src/app/checkup/detail/[id]/page.tsx        (redirect to /chat/)
- h5-web/src/app/checkup/page.tsx                    (fallback redirect to /chat/)
- h5-web/src/app/checkup/result/[id]/page.tsx       (redirect to /chat/)
- h5-web/next.config.js                              (added 301 redirects)
- admin-web/src/app/(admin)/checkup-details/page.tsx (9-grid + PreviewGroup)
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

# container short names per docker-compose.yml
C_BACKEND = f'{DEPLOY_ID}-backend'
C_H5 = f'{DEPLOY_ID}-h5'
C_ADMIN = f'{DEPLOY_ID}-admin'

FILES = [
    'backend/app/api/chat.py',
    'backend/scripts/migrate_checkup_multi_image.py',
    'backend/tests/test_multi_image_session_fields.py',
    'h5-web/src/app/chat/[sessionId]/page.tsx',
    'h5-web/src/app/checkup/chat/[sessionId]/page.tsx',
    'h5-web/src/app/checkup/compare/select/page.tsx',
    'h5-web/src/app/checkup/detail/[id]/page.tsx',
    'h5-web/src/app/checkup/page.tsx',
    'h5-web/src/app/checkup/result/[id]/page.tsx',
    'h5-web/next.config.js',
    'admin-web/src/app/(admin)/checkup-details/page.tsx',
]


def ensure_remote_dir(sftp, ssh, remote_path: str) -> None:
    """Create parent dirs for remote_path if missing. Uses mkdir -p via ssh."""
    parent = os.path.dirname(remote_path)
    run_cmd(ssh, f'mkdir -p "{parent}"', timeout=30)


def main() -> int:
    print('[deploy] connecting to server ...')
    ssh = create_client()
    sftp = ssh.open_sftp()

    try:
        # ---- 1. upload files ----
        for rel in FILES:
            local_path = os.path.join(LOCAL_ROOT, rel.replace('/', os.sep))
            remote_path = f'{REMOTE_ROOT}/{rel}'
            if not os.path.isfile(local_path):
                print(f'[deploy] ERROR local not found: {local_path}')
                return 1
            ensure_remote_dir(sftp, ssh, remote_path)
            print(f'[deploy] upload {rel}')
            sftp.put(local_path, remote_path)

        sftp.close()

        # ---- 2. restart backend (only fields added, no migration) ----
        print('\n[deploy] restart backend container ...')
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'docker compose restart backend 2>&1 | tail -20'
        )
        out, err, code = run_cmd(ssh, cmd, timeout=180)
        print(out)
        if err:
            print('STDERR:', err)
        print('[deploy] sleep 10s for backend to be ready ...')
        time.sleep(10)

        # ---- 3. rebuild h5-web ----
        print('\n[deploy] rebuild h5-web container ...')
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'docker compose build h5-web 2>&1 | tail -50'
        )
        out, err, code = run_cmd(ssh, cmd, timeout=1800)
        print(out)
        if err:
            print('STDERR:', err)
        if code != 0:
            print(f'[deploy] h5-web build exit code: {code}')
            return code
        out, err, code = run_cmd(
            ssh,
            f'cd {REMOTE_ROOT} && docker compose up -d --no-deps h5-web 2>&1 | tail -20',
            timeout=180,
        )
        print(out)

        # ---- 4. rebuild admin-web ----
        print('\n[deploy] rebuild admin-web container ...')
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'docker compose build admin-web 2>&1 | tail -50'
        )
        out, err, code = run_cmd(ssh, cmd, timeout=1800)
        print(out)
        if err:
            print('STDERR:', err)
        if code != 0:
            print(f'[deploy] admin-web build exit code: {code}')
            return code
        out, err, code = run_cmd(
            ssh,
            f'cd {REMOTE_ROOT} && docker compose up -d --no-deps admin-web 2>&1 | tail -20',
            timeout=180,
        )
        print(out)

        # ---- 5. wait 30s & status ----
        print('\n[deploy] sleep 30s then check containers ...')
        time.sleep(30)
        out, err, _ = run_cmd(
            ssh,
            f'docker ps --filter name={DEPLOY_ID}- --format "{{{{.Names}}}}\\t{{{{.Status}}}}"',
            timeout=60,
        )
        print(out)

        # ---- 6. run backfill migration (dry-run then apply) ----
        print('\n[deploy] run migrate_checkup_multi_image --dry-run ...')
        # Try module import first
        dry_cmd_mod = (
            f'docker exec {C_BACKEND} python -m scripts.migrate_checkup_multi_image --dry-run 2>&1 | tail -40'
        )
        out, err, code = run_cmd(ssh, dry_cmd_mod, timeout=180)
        print(out)
        if err:
            print('STDERR:', err)
        dry_ok = code == 0 and 'Error' not in out and 'Traceback' not in out

        if not dry_ok:
            print('[deploy] module form failed, trying script path form ...')
            dry_cmd_path = (
                f'docker exec {C_BACKEND} sh -c "cd /app && python scripts/migrate_checkup_multi_image.py --dry-run" 2>&1 | tail -40'
            )
            out, err, code = run_cmd(ssh, dry_cmd_path, timeout=180)
            print(out)
            if err:
                print('STDERR:', err)
            dry_ok = code == 0 and 'Error' not in out and 'Traceback' not in out

        if dry_ok:
            print('\n[deploy] apply migrate_checkup_multi_image ...')
            apply_cmd = (
                f'docker exec {C_BACKEND} python -m scripts.migrate_checkup_multi_image 2>&1 | tail -40'
            )
            out, err, code = run_cmd(ssh, apply_cmd, timeout=300)
            print(out)
            if err:
                print('STDERR:', err)
            if code != 0 or 'Traceback' in out:
                print('[deploy] module apply failed, trying script path form ...')
                apply_cmd2 = (
                    f'docker exec {C_BACKEND} sh -c "cd /app && python scripts/migrate_checkup_multi_image.py" 2>&1 | tail -40'
                )
                out, err, code = run_cmd(ssh, apply_cmd2, timeout=300)
                print(out)
                if code != 0 or 'Traceback' in out:
                    print('[deploy] WARNING: backfill did not succeed — needs manual run. Not blocking deploy verification.')
        else:
            print('[deploy] WARNING: dry-run failed in both forms — skipping actual backfill. Needs manual run.')

        # ---- 7. backend recent errors ----
        print('\n[deploy] backend recent logs (last 40 lines errors) ...')
        out, err, _ = run_cmd(
            ssh,
            f'docker logs --tail 80 {C_BACKEND} 2>&1 | grep -E "ERROR|Traceback|Exception" | tail -20 || true',
            timeout=30,
        )
        print(out or '(no errors found)')

        return 0
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
