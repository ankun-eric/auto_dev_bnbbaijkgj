"""Deeper fix for /api/products 500. Verify file content in container, then restart."""
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
        # Check: is the file on host updated?
        run(ssh, f'grep -n "selectinload(Product.skus)" {REMOTE_ROOT}/backend/app/api/products.py')

        # Check the file actually inside the container
        run(ssh, f'docker exec {DEPLOY_ID}-backend grep -n "selectinload(Product.skus)" /app/app/api/products.py || echo "NOT-IN-CONTAINER"')

        # The container may use the baked-in image (not bind mounted). Check docker-compose.prod.yml
        run(ssh, f'grep -n "volumes\\|backend:" {REMOTE_ROOT}/docker-compose.prod.yml | head -40')

        # Likely no bind mount -> need to rebuild backend image
        print('\n=== Rebuilding backend (no cache for api dir) ===')
        run(ssh, f'cd {REMOTE_ROOT} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -20', timeout=1200)
        run(ssh, f'cd {REMOTE_ROOT} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend 2>&1 | tail -20', timeout=300)

        time.sleep(15)
        run(ssh, f'docker exec {DEPLOY_ID}-backend grep -n "selectinload(Product.skus)" /app/app/api/products.py')

        # Wait for backend ready
        for i in range(10):
            out, _, c = run_cmd(ssh, f'curl -sS -o /dev/null -w "%{{http_code}}" "{BASE_URL}/api/health"', timeout=30)
            if out.strip() == '200':
                break
            time.sleep(3)

        # Verify
        run(ssh, f'curl -sS -o /tmp/p.json -w "api_products=%{{http_code}}\\n" "{BASE_URL}/api/products?page=1&page_size=5" && head -c 400 /tmp/p.json')
        run(ssh, f'docker logs --tail 40 {DEPLOY_ID}-backend 2>&1 | tail -40')

        # Final URL checks
        urls = [
            f'{BASE_URL}/',
            f'{BASE_URL}/h5/',
            f'{BASE_URL}/api/health',
            f'{BASE_URL}/api/products?page=1&page_size=5',
            f'{BASE_URL}/admin/product-system/products',
        ]
        print('\n=== Final check ===')
        for u in urls:
            run(ssh, f'curl -sS -o /dev/null -w "%{{http_code}}\\n" -L "{u}"')
    finally:
        ssh.close()

if __name__ == '__main__':
    main()
