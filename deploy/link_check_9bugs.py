"""9-Bugs v1 全量链接可达性验证脚本。

验证标准：HTTP 2xx / 3xx (301/302/307/308) / 401 / 403 视为可达
(401/403 对于登录保护页与 API 是正常的)。

输出 JSON 报告到 deploy/link_check_9bugs_report.json。
"""
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print('请先 pip install requests')
    sys.exit(1)

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
UA = 'Mozilla/5.0 (LinkCheck 9-bugs-v1)'
TIMEOUT = 15

# 可达判定集合
OK_STATUSES = {200, 301, 302, 304, 307, 308, 401, 403}

TARGETS = [
    # ---------- H5 前端 ----------
    {'cat': 'h5', 'path': '/', 'note': 'H5 根页（可能重定向）'},
    {'cat': 'h5', 'path': '/login', 'note': 'H5 登录页'},
    {'cat': 'h5', 'path': '/my-coupons', 'note': '我的优惠券(本次修复)'},
    {'cat': 'h5', 'path': '/points', 'note': '我的积分(本次修复)'},
    {'cat': 'h5', 'path': '/points/mall', 'note': '积分商城(本次修复)'},
    {'cat': 'h5', 'path': '/profile', 'note': '我的首页(本次修复)'},
    {'cat': 'h5', 'path': '/health-profile', 'note': '健康档案'},
    {'cat': 'h5', 'path': '/tcm', 'note': '中医养生'},

    # ---------- admin-web PC ----------
    {'cat': 'admin', 'path': '/admin/', 'note': 'admin 首页(本次修复)'},
    {'cat': 'admin', 'path': '/admin/login', 'note': 'admin 登录页'},

    # ---------- 后端 API ----------
    {'cat': 'api', 'path': '/api/health', 'note': '健康检查', 'expect_ok': True},
    {'cat': 'api', 'path': '/api/home-config', 'note': '首页配置'},
    {'cat': 'api', 'path': '/api/coupons/mine', 'note': '我的优惠券(401 预期)'},
    {'cat': 'api', 'path': '/api/coupons/summary', 'note': '优惠券合计(401 预期)'},
    {'cat': 'api', 'path': '/api/points/summary', 'note': '积分汇总(401 预期)'},
    {'cat': 'api', 'path': '/api/points/balance', 'note': '积分余额(401 预期)'},
    {'cat': 'api', 'path': '/api/points/tasks', 'note': '积分任务(401 预期)'},
    {'cat': 'api', 'path': '/api/constitution/archive', 'note': '健康档案(401 预期)'},
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
    reachable = status in OK_STATUSES
    return {
        'category': target['cat'],
        'path': target['path'],
        'url': url,
        'status': status,
        'reachable': reachable,
        'note': target.get('note', ''),
        'error': err,
    }


def main():
    session = requests.Session()
    results = []
    print(f'🔍 共 {len(TARGETS)} 个链接待检查')
    print('=' * 80)
    for t in TARGETS:
        r = check_one(session, t)
        flag = '✅' if r['reachable'] else '❌'
        err = f' err={r["error"]}' if r['error'] else ''
        print(f'{flag} [{r["status"]:>3}] {r["category"]:<6} {r["path"]:<40}  {r["note"]}{err}')
        results.append(r)

    total = len(results)
    ok = sum(1 for r in results if r['reachable'])
    print('=' * 80)
    print(f'✅ 可达 {ok}/{total}   ❌ 失败 {total - ok}/{total}')

    failed = [r for r in results if not r['reachable']]
    if failed:
        print('\n失败明细：')
        for r in failed:
            print(f'  ❌ {r["path"]}  status={r["status"]}  err={r["error"]}')

    report = {
        'deploy_id': DEPLOY_ID,
        'base_url': BASE_URL,
        'total': total,
        'passed': ok,
        'failed': total - ok,
        'all_passed': total == ok,
        'results': results,
    }
    report_path = Path(__file__).parent / 'link_check_9bugs_report.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\n📄 报告写入: {report_path}')

    sys.exit(0 if total == ok else 1)


if __name__ == '__main__':
    main()
