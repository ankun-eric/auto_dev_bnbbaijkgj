"""Diagnose h5 404 + api/products 500 after product-modal-v2 deploy."""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'

def run(ssh, cmd, timeout=120):
    print(f'\n$ {cmd}')
    o, e, c = run_cmd(ssh, cmd, timeout=timeout)
    if o.strip(): print(o)
    if e.strip(): print('STDERR:', e)
    print(f'[exit {c}]')
    return o, e, c

def main():
    ssh = create_client()
    try:
        print('=== backend recent logs (for /api/products 500) ===')
        run(ssh, f'docker logs --tail 150 {DEPLOY_ID}-backend 2>&1 | tail -150')

        print('=== hit /api/products from inside backend ===')
        run(ssh, f'docker exec {DEPLOY_ID}-backend curl -sS -o /tmp/prod.txt -w "code=%{{http_code}}\\n" "http://localhost:8000/api/products?page=1&page_size=5" && docker exec {DEPLOY_ID}-backend cat /tmp/prod.txt | head -100')

        print('=== inspect backend app dir (to find correct module path) ===')
        run(ssh, f'docker exec {DEPLOY_ID}-backend ls /app')
        run(ssh, f'docker exec {DEPLOY_ID}-backend ls /app/app')
        run(ssh, f'docker exec {DEPLOY_ID}-backend find /app -maxdepth 4 -name "session.py" 2>/dev/null | head -5')

        print('=== h5 container logs + probe port 3001 ===')
        run(ssh, f'docker logs --tail 80 {DEPLOY_ID}-h5 2>&1 | tail -80')
        run(ssh, f'docker exec {DEPLOY_ID}-h5 wget -qO- http://localhost:3001/ 2>&1 | head -5 || echo "-- try 3000 --"')
        run(ssh, f'docker exec {DEPLOY_ID}-h5 wget -qO- http://localhost:3000/ 2>&1 | head -5 || true')
        run(ssh, f'docker exec {DEPLOY_ID}-h5 sh -c "netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null"')

        print('=== gateway routes for this deploy ===')
        run(ssh, f'ls /home/ubuntu/gateway/conf.d/ 2>&1 | head')
        run(ssh, f'grep -l {DEPLOY_ID} /home/ubuntu/gateway/conf.d/* 2>/dev/null | head')

        print('=== gateway curl from inside gateway ===')
        run(ssh, f'docker exec gateway curl -sS -o /dev/null -w "code=%{{http_code}}\\n" "http://{DEPLOY_ID}-h5:3001/" ')
        run(ssh, f'docker exec gateway curl -sS -o /dev/null -w "code=%{{http_code}}\\n" "http://{DEPLOY_ID}-h5:3000/" ')
        run(ssh, f'docker exec gateway curl -sS -o /dev/null -w "code=%{{http_code}}\\n" "http://{DEPLOY_ID}-backend:8000/api/products?page=1&page_size=5" ')

    finally:
        ssh.close()

if __name__ == '__main__':
    main()
