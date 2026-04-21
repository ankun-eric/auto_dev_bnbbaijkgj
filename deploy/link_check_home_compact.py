"""首页顶部紧凑化 - 全量链接可达性验证。

对 H5 所有核心路由、Admin、主要后端 API 进行 curl 探测，
输出结果到 link_check_home_compact_report.json。
"""
import json
import sys
import time

sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'

# 覆盖：首页核心及其跳转目标（city-select, search, scan, messages）+ 基础 API
PATHS = [
    '/api/health',
    '/api/home-config',
    '/api/home-banners',
    '/api/home-menus',
    '/api/content/articles?page=1&page_size=3',
    '/api/notices/active',
    '/api/messages/unread-count',
    '/api/settings/logo',
    '/',
    '/login',
    '/home',
    '/city-select',
    '/search',
    '/scan',
    '/messages',
    '/profile',
    '/admin/',
    '/admin/login',
]


def main():
    ssh = create_client()
    results = []
    try:
        for p in PATHS:
            full = f'{BASE_URL}{p}'
            out, _, _ = run_cmd(
                ssh,
                f'curl -s -o /dev/null -w "%{{http_code}}" -L -A "Mozilla/5.0 LinkCheck" '
                f'--max-time 20 "{full}"',
                timeout=30,
            )
            code = out.strip() or '000'
            ok = code in ('200', '401', '403', '302', '307')
            mark = 'OK' if ok else 'FAIL'
            print(f'  [{code}] {mark:<5} {p}')
            results.append({'path': p, 'url': full, 'status': code, 'ok': ok})
            time.sleep(0.2)

        passed = sum(1 for r in results if r['ok'])
        total = len(results)
        print(f'\nSUMMARY: {passed}/{total} passed')

        report = {
            'base_url': BASE_URL,
            'total': total,
            'passed': passed,
            'failed': total - passed,
            'results': results,
        }
        with open('link_check_home_compact_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print('report -> link_check_home_compact_report.json')

        if passed != total:
            sys.exit(1)
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
