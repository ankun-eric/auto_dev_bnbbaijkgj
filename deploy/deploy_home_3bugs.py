"""Home 三个 Bug 修复一键部署脚本。

变更范围：
- flutter_app/lib/services/api_service.dart (仅影响 APK 编译)
- flutter_app/lib/screens/home/home_screen.dart (仅影响 APK)
- h5-web/src/app/(tabs)/home/page.tsx
- h5-web/src/lib/useHomeConfig.ts
- miniprogram/pages/home/index.js/wxml (小程序包，不影响服务端)

服务端需重建的容器：h5-web（因代码变更影响构建）。
后端/admin-web 未变更，无需重建，但为保险仅 restart backend 以清理缓存。
"""
import sys
import time

sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
PROJ_DIR = f'/home/ubuntu/{DEPLOY_ID}'
COMPOSE_FILE = 'docker-compose.prod.yml'

SERVICES_TO_REBUILD = ['h5-web']


def step(title):
    print('\n' + '=' * 60)
    print(f'> {title}')
    print('=' * 60, flush=True)


def exec_sh(ssh, cmd, timeout=600, check=True):
    short = cmd[:240] + ('...' if len(cmd) > 240 else '')
    print(f'$ {short}', flush=True)
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out.strip():
        print(out[-4000:])
    if err.strip():
        print(f'[stderr] {err[-2000:]}')
    print(f'[exit={code}]', flush=True)
    if check and code != 0:
        raise SystemExit(f'FAIL exit={code}: {cmd[:120]}')
    return out, err, code


def main():
    ssh = create_client()
    try:
        step('1. Git pull latest (master)')
        exec_sh(
            ssh,
            f'cd {PROJ_DIR} && git fetch origin master && '
            f'git reset --hard origin/master && git log -1 --oneline',
            timeout=180,
        )

        step('2. docker compose services')
        exec_sh(
            ssh,
            f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} config --services',
            check=False,
        )

        for svc in SERVICES_TO_REBUILD:
            step(f'3. Rebuild + Up: {svc}')
            _, _, code = exec_sh(
                ssh,
                f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} up -d --build --no-deps {svc}',
                timeout=1500,
                check=False,
            )
            if code != 0:
                print(f'[warn] {svc} first build failed, retry --no-cache once')
                exec_sh(
                    ssh,
                    f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache {svc} && '
                    f'docker compose -f {COMPOSE_FILE} up -d --no-deps {svc}',
                    timeout=1800,
                    check=True,
                )

        step('4. wait containers healthy')
        for i in range(30):
            out, _, _ = run_cmd(
                ssh,
                f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} ps '
                f'--format "table {{{{.Name}}}}\\t{{{{.State}}}}\\t{{{{.Status}}}}"',
            )
            print(out)
            if 'unhealthy' not in out and 'starting' not in out and 'Restarting' not in out:
                print(f'OK all containers ready ({i*5}s)')
                break
            time.sleep(5)
        else:
            print('[warn] health wait timeout 150s, continue')

        step('5. gateway network + reload')
        exec_sh(
            ssh,
            f'docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true; '
            f'docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload',
            check=False,
        )

        step('6. quick probes (home related)')
        probes = [
            '/api/health',
            '/api/home-config',
            '/api/home-banners',
            '/api/home-menus',
            '/api/content/articles?page=1&page_size=3',
            '/',
            '/login',
        ]
        for p in probes:
            full = f'{BASE_URL}{p}'
            out, _, _ = run_cmd(
                ssh,
                f'curl -s -o /dev/null -w "%{{http_code}}" -L -A "Mozilla/5.0 DeployCheck" '
                f'--max-time 15 "{full}"',
                timeout=30,
            )
            print(f'  [{out.strip() or "000"}] {p}')

        print('\nDEPLOY DONE. run link_check_home_3bugs.py for full check.')

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
