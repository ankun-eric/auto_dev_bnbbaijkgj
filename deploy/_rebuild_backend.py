import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd
import time

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'

ssh = create_client()
try:
    print('[rebuild] build backend ...')
    out, err, code = run_cmd(
        ssh,
        f'cd {REMOTE_ROOT} && docker compose build backend 2>&1 | tail -30',
        timeout=1200,
    )
    print(out)
    if code != 0:
        print(f'ERROR build exit code {code}')
        sys.exit(code)

    print('[rebuild] up -d --no-deps backend ...')
    out, _, _ = run_cmd(
        ssh,
        f'cd {REMOTE_ROOT} && docker compose up -d --no-deps backend 2>&1 | tail -10',
        timeout=180,
    )
    print(out)

    print('[rebuild] wait 15s ...')
    time.sleep(15)

    out, _, _ = run_cmd(
        ssh,
        f'docker logs --tail 40 {DEPLOY_ID}-backend 2>&1 | tail -20',
        timeout=30,
    )
    print(out)
finally:
    ssh.close()
