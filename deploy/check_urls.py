import requests, sys, json
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE = 'https://chat.benne-ai.com'
urls = [
    ('H5首页', f'{BASE}/'),
    ('H5 AI首页', f'{BASE}/ai-home'),
    ('H5 登录', f'{BASE}/login'),
    ('H5 健康档案', f'{BASE}/health-profile'),
    ('H5 成员中心', f'{BASE}/member-center'),
    ('H5 消息', f'{BASE}/messages'),
    ('H5 设备', f'{BASE}/devices'),
    ('H5 脑力游戏', f'{BASE}/brain-game'),
    ('H5 关怀版', f'{BASE}/care-ai-home'),
    ('H5 安全绳', f'{BASE}/care-safety-rope'),
    ('H5 邀请', f'{BASE}/family-auth'),
    ('H5 结算', f'{BASE}/checkout'),
    ('H5 预约', f'{BASE}/appointment'),
    ('H5 卡片', f'{BASE}/cards'),
    ('Admin首页', f'{BASE}/admin/'),
    ('Admin 登录', f'{BASE}/admin/login'),
    ('API 健康检查', f'{BASE}/api/health'),
    ('API 系统时间', f'{BASE}/api/system-info'),
    ('API 系统消息', f'{BASE}/api/system-messages'),
]

results = []
for name, url in urls:
    try:
        r = requests.get(url, timeout=15, verify=False, allow_redirects=True)
        status = 'OK' if r.status_code in (200,302,303,307,308) else f'ERR:{r.status_code}'
        results.append({'name': name, 'url': url, 'status': status, 'code': r.status_code})
    except Exception as e:
        results.append({'name': name, 'url': url, 'status': f'FAIL:{str(e)[:60]}', 'code': 0})

ok = sum(1 for r in results if r['status'] == 'OK')
fail = len(results) - ok
print(f'\nTotal: {len(results)}, OK: {ok}, FAIL: {fail}')
for r in results:
    print(f"  [{r['status']}] {r['name']}: {r['url']}")
