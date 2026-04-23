"""Fix backend api/products 500 (N+1 lazy-load of skus) and verify h5 route.

1. upload fixed backend/app/api/products.py to server
2. docker compose restart backend
3. verify: curl api/products
4. inspect h5 gateway conf and test /h5/ route
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def run(ssh, cmd, timeout=180):
    print(f'$ {cmd}')
    o, e, c = run_cmd(ssh, cmd, timeout=timeout)
    if o.strip(): print(o)
    if e.strip(): print('STDERR:', e)
    print(f'[exit {c}]')
    return o, e, c

def main():
    ssh = create_client()
    try:
        # Upload patched file
        sftp = ssh.open_sftp()
        local = os.path.join(LOCAL_ROOT, 'backend', 'app', 'api', 'products.py')
        remote = f'{REMOTE_ROOT}/backend/app/api/products.py'
        print(f'upload {local} -> {remote}')
        sftp.put(local, remote)
        sftp.close()

        run(ssh, f'cd {REMOTE_ROOT} && docker compose -f docker-compose.prod.yml restart backend 2>&1 | tail -10', timeout=120)
        time.sleep(12)

        run(ssh, f'docker logs --tail 30 {DEPLOY_ID}-backend 2>&1 | tail -30')

        # Verify via gateway
        run(ssh, f'docker exec gateway curl -sS -o /dev/null -w "api_products=%{{http_code}}\\n" "http://{DEPLOY_ID}-backend:8000/api/products?page=1&page_size=5"')
        run(ssh, f'curl -sS -o /dev/null -w "ext_api_products=%{{http_code}}\\n" "{BASE_URL}/api/products?page=1&page_size=5"')

        # Inspect h5 route in gateway conf
        conf_path = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf'
        run(ssh, f'cat {conf_path}')

        # Hit the h5 via gateway WITH trailing slash AND without
        run(ssh, f'curl -sS -o /dev/null -w "ext_h5_slash=%{{http_code}}\\n" "{BASE_URL}/h5/"')
        run(ssh, f'curl -sS -o /dev/null -w "ext_h5_noslash=%{{http_code}}\\n" -L "{BASE_URL}/h5"')
        # Maybe the app is at root under /autodev/<id>/h5/... ; try /h5/index
        run(ssh, f'curl -sS -o /tmp/h5.html -w "ext_h5_root=%{{http_code}}\\n" "{BASE_URL}/h5/" && wc -l /tmp/h5.html && head -c 400 /tmp/h5.html')
        # Directly via container to see if basePath is /autodev/<id>/h5
        run(ssh, f'docker exec gateway curl -sS -o /dev/null -w "direct_root=%{{http_code}}\\n" "http://{DEPLOY_ID}-h5:3001/"')
        run(ssh, f'docker exec gateway curl -sS -o /dev/null -w "direct_basepath=%{{http_code}}\\n" "http://{DEPLOY_ID}-h5:3001/autodev/{DEPLOY_ID}/h5/"')
        run(ssh, f'docker exec gateway curl -sS -o /dev/null -w "direct_h5path=%{{http_code}}\\n" "http://{DEPLOY_ID}-h5:3001/h5/"')
    finally:
        ssh.close()

if __name__ == '__main__':
    main()
