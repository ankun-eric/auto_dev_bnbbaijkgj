"""v8 内容管理优化一键部署脚本。

变更范围（需要重建的服务）：
- backend （模型 / 迁移 / 新 API / 移除 video 端点）
- admin-web （资讯/分类/文章管理页面）
- h5-web （首页资讯板块 / 资讯页面 / 文章富文本）

miniprogram / flutter 本阶段暂不变更。
"""
import sys
import time

sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
PROJ_DIR = f'/home/ubuntu/{DEPLOY_ID}'
COMPOSE_FILE = 'docker-compose.prod.yml'

SERVICES_TO_REBUILD = ['backend', 'admin-web', 'h5-web']


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
        step('1. Git pull latest (master) - retry on tls errors')
        import time as _t
        for i in range(8):
            _, _, code = exec_sh(
                ssh,
                f'cd {PROJ_DIR} && timeout 90 git fetch origin master && '
                f'git reset --hard origin/master && git log -1 --oneline',
                timeout=120, check=False,
            )
            if code == 0:
                break
            print(f'git fetch attempt {i+1} failed, retry 15s')
            _t.sleep(15)
        else:
            raise SystemExit('git pull failed after 8 attempts')

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
                timeout=1800,
                check=False,
            )
            if code != 0:
                print(f'[warn] {svc} first build failed, retry --no-cache once')
                exec_sh(
                    ssh,
                    f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache {svc} && '
                    f'docker compose -f {COMPOSE_FILE} up -d --no-deps {svc}',
                    timeout=2400,
                    check=True,
                )

        step('4. wait containers healthy')
        for i in range(40):
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
            print('[warn] health wait timeout 200s, continue')

        step('5. gateway network + reload')
        exec_sh(
            ssh,
            f'docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true; '
            f'docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload',
            check=False,
        )

        step('6. quick probes (v8 content related)')
        probes = [
            '/api/health',
            '/api/content/articles?page=1&page_size=3',
            '/api/content/article-categories',
            '/api/content/news?page=1&page_size=5',
            '/api/content/news/latest?limit=5',
            '/',
            '/login',
            '/news',
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

        step('7. backend logs tail (v8 migration)')
        out, _, _ = run_cmd(
            ssh,
            f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} logs --tail=80 backend',
            timeout=30,
        )
        print(out[-4000:])

        print('\nDEPLOY v8 content DONE.')

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
