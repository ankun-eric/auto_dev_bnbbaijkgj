"""Home 三个 Bug 修复 全量链接可达性验证脚本。

可达判定：HTTP 2xx / 3xx / 401 / 403。
"""
import json
import sys
from pathlib import Path

import requests

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
UA = 'Mozilla/5.0 (LinkCheck home-3bugs)'
TIMEOUT = 15

OK_STATUSES = {200, 301, 302, 304, 307, 308, 401, 403}

TARGETS = [
    # ====== 本次修复重点 ======
    {'cat': 'api', 'path': '/api/home-config', 'note': '首页配置(菜单列数)'},
    {'cat': 'api', 'path': '/api/home-banners', 'note': '首页 Banner 列表(可为空)'},
    {'cat': 'api', 'path': '/api/home-menus', 'note': '首页菜单列表(可为空)'},
    {'cat': 'api', 'path': '/api/content/articles?page=1&page_size=3', 'note': '健康知识文章列表'},
    {'cat': 'api', 'path': '/api/content/articles', 'note': '健康知识文章列表(默认)'},

    # ====== H5 前端 ======
    {'cat': 'h5', 'path': '/', 'note': 'H5 根页'},
    {'cat': 'h5', 'path': '/home', 'note': 'H5 首页 tab'},
    {'cat': 'h5', 'path': '/login', 'note': 'H5 登录页'},
    {'cat': 'h5', 'path': '/profile', 'note': 'H5 我的'},
    {'cat': 'h5', 'path': '/unified-orders', 'note': 'H5 订单'},
    {'cat': 'h5', 'path': '/points', 'note': 'H5 积分'},
    {'cat': 'h5', 'path': '/my-coupons', 'note': 'H5 我的优惠券'},
    {'cat': 'h5', 'path': '/tcm', 'note': 'H5 中医养生'},
    {'cat': 'h5', 'path': '/health-profile', 'note': '健康档案'},

    # ====== admin-web ======
    {'cat': 'admin', 'path': '/admin/', 'note': 'admin 首页'},
    {'cat': 'admin', 'path': '/admin/login', 'note': 'admin 登录页'},

    # ====== 后端通用 ======
    {'cat': 'api', 'path': '/api/health', 'note': '健康检查'},
    {'cat': 'api', 'path': '/api/coupons/mine', 'note': '我的优惠券(401 预期)'},
    {'cat': 'api', 'path': '/api/points/balance', 'note': '积分余额(401 预期)'},
]


def check_one(session, target):
    url = BASE_URL + target['path']
    try:
        r = session.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
            headers={'User-Agent': UA},
        )
        status = r.status_code
        err = None
    except requests.exceptions.RequestException as e:
        status = 0
        err = str(e)
    return {
        'category': target['cat'],
        'path': target['path'],
        'url': url,
        'status': status,
        'reachable': status in OK_STATUSES,
        'note': target.get('note', ''),
        'error': err,
    }


def main():
    session = requests.Session()
    results = []
    print(f'[Check] total={len(TARGETS)} links')
    print('=' * 90)
    for t in TARGETS:
        r = check_one(session, t)
        flag = 'OK' if r['reachable'] else 'FAIL'
        err = f' err={r["error"]}' if r['error'] else ''
        print(f'{flag:<4} [{r["status"]:>3}] {r["category"]:<6} {r["path"]:<48}  {r["note"]}{err}')
        results.append(r)

    total = len(results)
    ok = sum(1 for r in results if r['reachable'])
    print('=' * 90)
    print(f'pass={ok}/{total}   fail={total - ok}/{total}')

    failed = [r for r in results if not r['reachable']]
    if failed:
        print('\nFailed:')
        for r in failed:
            print(f'  FAIL {r["path"]}  status={r["status"]}  err={r["error"]}')

    report = {
        'deploy_id': DEPLOY_ID,
        'base_url': BASE_URL,
        'total': total,
        'passed': ok,
        'failed': total - ok,
        'all_passed': total == ok,
        'results': results,
    }
    Path(__file__).parent.joinpath('link_check_home_3bugs_report.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8'
    )

    sys.exit(0 if total == ok else 1)


if __name__ == '__main__':
    main()
