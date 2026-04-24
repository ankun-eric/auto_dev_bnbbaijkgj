"""探查远程服务器结构"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

ssh = create_client()
try:
    cmds = [
        f'ls -la /home/ubuntu/{DEPLOY_ID} 2>&1 | head -30',
        f'ls -la /home/ubuntu/{DEPLOY_ID}/h5-web 2>&1 | head -20',
        f'ls -la /home/ubuntu/ 2>&1 | head -20',
        f'docker ps --filter name={DEPLOY_ID}- --format "{{{{.Names}}}}\\t{{{{.Status}}}}"',
        f'cat /home/ubuntu/{DEPLOY_ID}/docker-compose.yml 2>&1 | head -80',
    ]
    for c in cmds:
        print('=' * 60)
        print('$', c)
        out, err, code = run_cmd(ssh, c, timeout=30)
        if out:
            print(out)
        if err:
            print('STDERR:', err)
finally:
    ssh.close()
