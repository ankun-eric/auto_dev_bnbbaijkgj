"""对账单管理重构部署脚本 v2 (2026-04-24)

远程目录不是 git 仓库，采用 SCP 直接上传 6 个变更文件，然后 rebuild backend + admin-web。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd  # type: ignore

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'
COMPOSE_FILE = 'docker-compose.prod.yml'
C_BACKEND = f'{DEPLOY_ID}-backend'
C_ADMIN = f'{DEPLOY_ID}-admin-web'

LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 相对 LOCAL_ROOT 的路径 -> 相对 REMOTE_ROOT 的路径
FILE_MAP = [
    ('backend/app/models/models.py', 'backend/app/models/models.py'),
    ('backend/app/services/schema_sync.py', 'backend/app/services/schema_sync.py'),
    ('backend/app/schemas/merchant_v1.py', 'backend/app/schemas/merchant_v1.py'),
    ('backend/app/api/merchant_v1.py', 'backend/app/api/merchant_v1.py'),
    ('admin-web/src/app/(admin)/layout.tsx', 'admin-web/src/app/(admin)/layout.tsx'),
    ('admin-web/src/app/(admin)/admin-settlements/page.tsx', 'admin-web/src/app/(admin)/admin-settlements/page.tsx'),
]


def banner(msg: str) -> None:
    print('\n' + '=' * 80)
    print(f'[deploy] {msg}')
    print('=' * 80, flush=True)


def main() -> int:
    banner('connecting to server ...')
    ssh = create_client()
    try:
        sftp = ssh.open_sftp()

        banner('upload 6 changed files')
        for rel_local, rel_remote in FILE_MAP:
            lp = os.path.join(LOCAL_ROOT, rel_local.replace('/', os.sep))
            rp = f'{REMOTE_ROOT}/{rel_remote}'
            size = os.path.getsize(lp)
            # 确保远程父目录存在
            parent = rp.rsplit('/', 1)[0]
            run_cmd(ssh, f'mkdir -p "{parent}"', timeout=10)
            sftp.put(lp, rp)
            print(f'  uploaded {rel_remote} ({size} bytes)')

        sftp.close()

        banner('verify uploaded files')
        out, _, _ = run_cmd(ssh, (
            f'grep -c "voucher_type\\|voucher_files" {REMOTE_ROOT}/backend/app/models/models.py && '
            f'grep -c "_sync_settlement_proof_schema" {REMOTE_ROOT}/backend/app/services/schema_sync.py && '
            f'grep -c "/admin/settlements" {REMOTE_ROOT}/backend/app/api/merchant_v1.py && '
            f'wc -l {REMOTE_ROOT}/admin-web/src/app/\\(admin\\)/admin-settlements/page.tsx'
        ), timeout=30)
        print(out)

        banner('docker compose build backend admin-web (long, ~5 min)')
        cmd = f'cd {REMOTE_ROOT} && docker compose -f {COMPOSE_FILE} build backend admin-web 2>&1 | tail -150'
        out, err, code = run_cmd(ssh, cmd, timeout=1800)
        print(out)
        if code != 0:
            print(f'[deploy] build exit={code}')
            if err:
                print('STDERR:', err[-2000:])
            return code

        banner('docker compose up -d --no-deps backend admin-web')
        cmd = f'cd {REMOTE_ROOT} && docker compose -f {COMPOSE_FILE} up -d --no-deps backend admin-web 2>&1 | tail -30'
        out, err, code = run_cmd(ssh, cmd, timeout=300)
        print(out)
        if code != 0:
            print(f'[deploy] up exit={code}')
            print('STDERR:', err[-2000:] if err else '')
            return code

        banner('sleep 25s then inspect containers')
        time.sleep(25)
        out, _, _ = run_cmd(
            ssh,
            f'docker ps --filter name={DEPLOY_ID}- --format "{{{{.Names}}}}\\t{{{{.Status}}}}"',
            timeout=30,
        )
        print(out)

        banner('backend last 100 lines (schema_sync check)')
        out, _, _ = run_cmd(ssh, f'docker logs --tail 100 {C_BACKEND} 2>&1', timeout=60)
        print(out)

        banner('admin-web last 40 lines')
        out, _, _ = run_cmd(ssh, f'docker logs --tail 40 {C_ADMIN} 2>&1', timeout=60)
        print(out)

        banner('verify settlement_payment_proofs schema (new columns)')
        py = (
            'import os;'
            'from sqlalchemy import create_engine,text;'
            'url=os.environ.get(\"DATABASE_URL\");'
            'print(\"DATABASE_URL=\",url);'
            'e=create_engine(url);'
            'c=e.connect();'
            'rows=c.execute(text(\"SHOW COLUMNS FROM settlement_payment_proofs\")).fetchall();'
            '[print(r[0],r[1],r[2],r[3]) for r in rows];'
            'c.close()'
        )
        cmd = f"docker exec {C_BACKEND} python -c '{py}'"
        out, err, code = run_cmd(ssh, cmd, timeout=60)
        print('STDOUT:')
        print(out)
        if err:
            print('STDERR:', err)

        return 0
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
