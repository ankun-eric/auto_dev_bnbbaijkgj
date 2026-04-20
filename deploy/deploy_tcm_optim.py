"""TCM 体质测评功能优化 — 一键部署：
1. 服务器 Git fetch+reset 拉取最新代码
2. 重启 backend 和 h5-web 容器
3. 等待 healthcheck 通过
4. 快速链接可达性检查
"""
import sys
import time
sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
PROJ_DIR = f'/home/ubuntu/{DEPLOY_ID}'


def step(title):
    print('\n' + '=' * 60)
    print(f'▶ {title}')
    print('=' * 60)


def exec_sh(ssh, cmd, timeout=600, check=True):
    print(f'$ {cmd[:220]}' + ('...' if len(cmd) > 220 else ''))
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print(f'[stderr] {err[-1500:]}')
    print(f'[exit={code}]')
    if check and code != 0:
        raise SystemExit(f'命令失败，退出码={code}')
    return out, err, code


def main():
    ssh = create_client()
    try:
        step('1. Git 拉取最新代码')
        exec_sh(
            ssh,
            f'cd {PROJ_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline',
        )

        step('2. 重启后端容器（重新构建镜像以拉取后端代码变更）')
        exec_sh(
            ssh,
            f'cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d --build --no-deps backend',
            timeout=900,
        )

        step('3. 重启 H5 前端容器（重新构建以编译新的 /tcm 页面）')
        exec_sh(
            ssh,
            f'cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d --build --no-deps h5-web',
            timeout=1200,
        )

        step('4. 等待容器健康检查')
        for i in range(24):
            out, _, _ = run_cmd(ssh, f'cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml ps --format "table {{{{.Name}}}}\\t{{{{.State}}}}\\t{{{{.Status}}}}"')
            print(out)
            if 'unhealthy' not in out and 'starting' not in out:
                print(f'✅ 所有容器就绪 (耗时 {i*5}s)')
                break
            time.sleep(5)
        else:
            print('⚠️ 容器健康检查超时，继续后续步骤')

        step('5. Gateway 重连项目网络 + 预热 reload（防 502）')
        exec_sh(
            ssh,
            f'docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true; '
            f'docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload',
            check=False,
        )

        step('6. 快速链路检查')
        key_links = [
            ('GET', '/api/health'),
            ('GET', '/api/tcm/diagnoses?page=1&page_size=5'),
            ('GET', '/api/constitution/archive'),
            ('GET', '/tcm'),
            ('GET', '/tcm/archive'),
        ]
        report = []
        for method, path in key_links:
            full = f'{BASE_URL}{path}'
            cmd = f'curl -s -o /dev/null -w "%{{http_code}}" -X {method} "{full}"'
            out, _, _ = run_cmd(ssh, cmd, timeout=30)
            code = out.strip() or '000'
            # 2xx / 3xx / 401(未鉴权API可达) / 405(方法不支持可达) 视为可达
            reachable = code.startswith('2') or code.startswith('3') or code in ('401', '403', '405')
            flag = '✅' if reachable else '❌'
            report.append((flag, code, method, path))
            print(f'{flag} {method} {path} → {code}')

        print('\n===== 链接检查汇总 =====')
        ok = sum(1 for r in report if r[0] == '✅')
        print(f'可达 {ok}/{len(report)}')
        for flag, code, m, p in report:
            print(f'  {flag} [{code}] {m} {p}')

        if ok == len(report):
            print('\n🎉 所有核心链接可达，部署成功！')
        else:
            print('\n⚠️ 存在不可达链接，需要排查')

    finally:
        ssh.close()


if __name__ == '__main__':
    main()
