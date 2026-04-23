"""Deploy product-modal v2 (5Tab + SKU + rich text + barcode + video + 强校验) via Git pull + rebuild.

Target commit: fe57e0b (ankun-eric/auto_dev_bnbbaijkgj)

Steps:
 1. git fetch origin && git reset --hard origin/master (on server)
 2. docker compose -f docker-compose.prod.yml config --services (probe service names)
 3. docker compose -f docker-compose.prod.yml build + up -d --force-recreate
 4. ensure gateway nginx connected to project network
 5. schema verify: products new cols + product_skus table
 6. curl 5 key URLs from within server, report HTTP status
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd  # type: ignore

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
COMPOSE_FILE = 'docker-compose.prod.yml'

KEY_URLS = [
    f'{BASE_URL}/',
    f'{BASE_URL}/h5/',
    f'{BASE_URL}/api/health',
    f'{BASE_URL}/api/products?page=1&page_size=5',
    f'{BASE_URL}/admin/product-system/products',
]


def banner(msg: str) -> None:
    print('\n' + '=' * 70)
    print(msg)
    print('=' * 70)


def run(ssh, cmd: str, *, timeout: int = 300, quiet: bool = False) -> tuple[str, str, int]:
    if not quiet:
        print(f'[exec] {cmd}')
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out.strip():
        print(out)
    if err.strip():
        print('STDERR:', err)
    if not quiet:
        print(f'[exit] {code}')
    return out, err, code


def main() -> int:
    banner('[1/7] SSH connect')
    ssh = create_client()
    try:
        run(ssh, 'whoami && hostname && date')

        banner('[2/7] Git pull latest code')
        run(
            ssh,
            f'cd {REMOTE_ROOT} && git fetch origin 2>&1 | tail -20',
            timeout=180,
        )
        run(
            ssh,
            f'cd {REMOTE_ROOT} && git reset --hard origin/master && git clean -fd && git log -1 --oneline',
            timeout=120,
        )

        banner('[3/7] Probe compose services')
        out, _, _ = run(
            ssh,
            f'cd {REMOTE_ROOT} && docker compose -f {COMPOSE_FILE} config --services',
            timeout=60,
        )
        services = [s.strip() for s in out.splitlines() if s.strip()]
        print(f'[services] {services}')

        # Identify which services to rebuild (backend + admin-web + h5-web)
        # Common name patterns
        wanted = []
        for key in ('backend', 'frontend', 'admin-web', 'adminweb', 'h5web', 'h5-web', 'h5'):
            for s in services:
                if s.lower() == key and s not in wanted:
                    wanted.append(s)
        # De-dup but keep some fallback
        if not wanted:
            wanted = services  # rebuild all
        print(f'[rebuild] {wanted}')

        banner('[4/7] docker compose build')
        run(
            ssh,
            (
                f'cd {REMOTE_ROOT} && '
                f'docker compose -f {COMPOSE_FILE} build {" ".join(wanted)} 2>&1 | tail -60'
            ),
            timeout=1800,
        )

        banner('[4/7] docker compose up -d --force-recreate')
        run(
            ssh,
            (
                f'cd {REMOTE_ROOT} && '
                f'docker compose -f {COMPOSE_FILE} up -d --force-recreate {" ".join(wanted)} 2>&1 | tail -60'
            ),
            timeout=600,
        )

        print('[wait] sleep 25s for containers to become healthy ...')
        time.sleep(25)

        run(ssh, f'cd {REMOTE_ROOT} && docker compose -f {COMPOSE_FILE} ps', timeout=60)

        banner('[5/7] Ensure gateway nginx on project network')
        # Find gateway container name
        gw_out, _, _ = run(
            ssh,
            'docker ps --format "{{.Names}}" | grep -Ei "nginx|gateway" || true',
            timeout=30,
        )
        gateway_name = None
        for line in gw_out.splitlines():
            name = line.strip()
            if name and DEPLOY_ID not in name:
                gateway_name = name
                break
        print(f'[gateway] detected: {gateway_name}')

        # Find project network
        net_out, _, _ = run(
            ssh,
            f'docker network ls --format "{{{{.Name}}}}" | grep {DEPLOY_ID} || true',
            timeout=30,
        )
        net_name = net_out.strip().splitlines()[0] if net_out.strip() else f'{DEPLOY_ID}_default'
        print(f'[network] project network: {net_name}')

        if gateway_name:
            run(
                ssh,
                f'docker network connect {net_name} {gateway_name} 2>&1 || echo "(already connected or conflict ok)"',
                timeout=60,
            )
            run(
                ssh,
                f'docker network inspect {net_name} --format "{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}"',
                timeout=30,
            )

        banner('[6/7] Verify backend schema (products + product_skus)')
        backend_name = f'{DEPLOY_ID}-backend'
        # Wait for backend to be really up
        for i in range(8):
            _, _, c = run(
                ssh,
                f'docker exec {backend_name} python -c "print(1)" 2>&1 | tail -5',
                timeout=30,
                quiet=True,
            )
            if c == 0:
                break
            print(f'[wait backend] retry {i+1}/8 ...')
            time.sleep(5)

        schema_cmd = (
            f'docker exec {backend_name} python -c "'
            'import asyncio\n'
            'from sqlalchemy import text\n'
            'from app.db.session import engine\n'
            'async def main():\n'
            '    async with engine.begin() as conn:\n'
            "        r = await conn.execute(text('DESCRIBE products'))\n"
            '        rows = r.fetchall()\n'
            "        wanted = ('product_code_list','spec_mode','main_video_url','selling_point','description_rich')\n"
            '        found = [row[0] for row in rows if row[0] in wanted]\n'
            "        print('products_new_cols:', found)\n"
            '        r = await conn.execute(text(\\\"SHOW TABLES LIKE \'product_skus\'\\\"))\n'
            "        print('product_skus:', r.fetchall())\n"
            '        r = await conn.execute(text(\\\"SHOW TABLES LIKE \'order_items\'\\\"))\n'
            "        if r.fetchall():\n"
            "            r = await conn.execute(text('DESCRIBE order_items'))\n"
            "            ors = [row[0] for row in r.fetchall() if row[0] in ('sku_id','sku_name')]\n"
            "            print('order_items_new_cols:', ors)\n"
            'asyncio.run(main())\n'
            '"'
        )
        out, err, code = run(ssh, schema_cmd, timeout=90)
        if code != 0 or 'products_new_cols' not in out:
            print('[schema] trying restart backend to retry schema_sync ...')
            run(ssh, f'docker restart {backend_name}', timeout=60)
            time.sleep(15)
            run(ssh, schema_cmd, timeout=90)

        banner('[7/7] Curl key URLs from inside server')
        results = {}
        for url in KEY_URLS:
            cmd = (
                f'curl -sS -o /dev/null -w "%{{http_code}}" -L --max-time 20 '
                f'-A "deploy-bot" "{url}"'
            )
            out, err, code = run(ssh, cmd, timeout=60, quiet=True)
            status = out.strip() or f'ERR:{err.strip()[:80]}'
            results[url] = status
            print(f'  {status}  {url}')

        banner('Summary')
        ok = True
        for url, status in results.items():
            marker = 'OK ' if status.startswith(('2', '3')) else 'FAIL'
            if not status.startswith(('2', '3')):
                ok = False
            print(f'{marker}  {status}  {url}')

        banner('Final container status')
        run(ssh, f'cd {REMOTE_ROOT} && docker compose -f {COMPOSE_FILE} ps', timeout=60)

        return 0 if ok else 2
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
