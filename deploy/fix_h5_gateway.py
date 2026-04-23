"""Add /h5/ redirect to gateway conf + verify."""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
CONF = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf'

def run(ssh, cmd, timeout=120):
    print(f'$ {cmd}')
    o, e, c = run_cmd(ssh, cmd, timeout=timeout)
    if o.strip(): print(o)
    if e.strip(): print('STDERR:', e)
    print(f'[exit {c}]')
    return o, e, c

REDIRECT_BLOCK = f"""
# AUTO: /h5 and /h5/ -> project root (h5 basePath is /autodev/{DEPLOY_ID})
location = /autodev/{DEPLOY_ID}/h5 {{
    return 301 /autodev/{DEPLOY_ID}/;
}}
location = /autodev/{DEPLOY_ID}/h5/ {{
    return 301 /autodev/{DEPLOY_ID}/;
}}
"""

def main():
    ssh = create_client()
    try:
        # Check if already added
        out, _, _ = run(ssh, f'grep -c "AUTO: /h5 and /h5/" {CONF} || true')
        if out.strip() and out.strip() != '0':
            print('redirect block already present')
        else:
            # Backup + append the block
            stamp = time.strftime('%Y%m%d%H%M%S')
            run(ssh, f'sudo cp {CONF} {CONF}.bak.h5redir.{stamp}')
            # Use here-doc append
            payload = REDIRECT_BLOCK.replace('"', '\\"')
            run(ssh, f'echo "{payload}" | sudo tee -a {CONF} > /dev/null')

        # Reload gateway
        run(ssh, 'docker exec gateway nginx -t 2>&1')
        run(ssh, 'docker exec gateway nginx -s reload 2>&1')
        time.sleep(2)

        # Verify
        run(ssh, f'curl -sS -o /dev/null -w "h5_slash=%{{http_code}} h5_final=%{{http_code}}\\n" -L "{BASE_URL}/h5/"')
        run(ssh, f'curl -sS -o /dev/null -w "h5_slash_norelink=%{{http_code}}\\n" "{BASE_URL}/h5/"')
        run(ssh, f'curl -sS -o /dev/null -w "root=%{{http_code}}\\n" "{BASE_URL}/"')
        run(ssh, f'curl -sS -o /dev/null -w "api_health=%{{http_code}}\\n" "{BASE_URL}/api/health"')
        run(ssh, f'curl -sS -o /dev/null -w "api_products=%{{http_code}}\\n" "{BASE_URL}/api/products?page=1&page_size=5"')
        run(ssh, f'curl -sS -o /dev/null -w "admin_products=%{{http_code}}\\n" "{BASE_URL}/admin/product-system/products"')
    finally:
        ssh.close()

if __name__ == '__main__':
    main()
