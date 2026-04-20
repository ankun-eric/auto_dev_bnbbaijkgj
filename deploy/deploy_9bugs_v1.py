"""9-Bugs v1 修复一键部署脚本。

变更范围：
- 后端：backend/app/api/coupons.py, points.py, models/models.py,
        services/register_service.py, schema_sync.py,
        services/member_code.py (新增)
- h5-web：优惠券/积分/积分商城/我的页
- admin-web：(admin)/layout.tsx, globals.css

流程：
1. SSH 登录服务器
2. git fetch + reset --hard origin/master
3. docker compose (prod) build+up backend、h5-web、admin-web
4. 等待容器健康
5. gateway-nginx reload
"""
import sys
import time
sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
PROJ_DIR = f'/home/ubuntu/{DEPLOY_ID}'
COMPOSE_FILE = 'docker-compose.prod.yml'

SERVICES_TO_REBUILD = ['backend', 'h5-web', 'admin-web']


def step(title):
    print('\n' + '=' * 60)
    print(f'▶ {title}')
    print('=' * 60, flush=True)


def exec_sh(ssh, cmd, timeout=600, check=True):
    print(f'$ {cmd[:240]}' + ('...' if len(cmd) > 240 else ''), flush=True)
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out.strip():
        print(out[-4000:])
    if err.strip():
        print(f'[stderr] {err[-2000:]}')
    print(f'[exit={code}]', flush=True)
    if check and code != 0:
        raise SystemExit(f'命令失败，退出码={code}: {cmd[:120]}')
    return out, err, code


def main():
    ssh = create_client()
    try:
        step('1. Git 拉取最新代码')
        exec_sh(
            ssh,
            f'cd {PROJ_DIR} && git fetch origin master && '
            f'git reset --hard origin/master && '
            f'git log -1 --oneline',
            timeout=180,
        )

        step('2. 查看 docker compose 服务列表 (确认 admin 服务名)')
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
                print(f'[warn] {svc} 首次 build 失败，尝试 --no-cache 一次')
                exec_sh(
                    ssh,
                    f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache {svc} && '
                    f'docker compose -f {COMPOSE_FILE} up -d --no-deps {svc}',
                    timeout=1800,
                    check=True,
                )

        step('4. 等待容器健康 / 就绪')
        for i in range(30):
            out, _, _ = run_cmd(
                ssh,
                f'cd {PROJ_DIR} && docker compose -f {COMPOSE_FILE} ps '
                f'--format "table {{{{.Name}}}}\\t{{{{.State}}}}\\t{{{{.Status}}}}"',
            )
            print(out)
            if 'unhealthy' not in out and 'starting' not in out and 'Restarting' not in out:
                print(f'✅ 所有容器就绪 (耗时 {i*5}s)')
                break
            time.sleep(5)
        else:
            print('⚠️ 容器健康检查超时 30*5=150s，继续')

        step('5. Gateway 网络连通 + reload')
        exec_sh(
            ssh,
            f'docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true; '
            f'docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload',
            check=False,
        )

        step('6. 快速健康探针')
        for p in ['/api/health', '/login', '/my-coupons', '/points', '/points/mall', '/admin/login']:
            full = f'{BASE_URL}{p}'
            out, _, _ = run_cmd(
                ssh,
                f'curl -s -o /dev/null -w "%{{http_code}}" -L -A "Mozilla/5.0 DeployCheck" --max-time 15 "{full}"',
                timeout=30,
            )
            print(f'  [{out.strip() or "000"}] {p}')

        print('\n🎉 部署流程完成，请运行 link_check_9bugs.py 做全量链接验证')

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
