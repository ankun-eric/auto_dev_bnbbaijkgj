import requests
import urllib3
urllib3.disable_warnings()

domain = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

tests = [
    ('GET', f'{domain}/api/care-v1/user-preferences', 'user-preferences (保留)'),
    ('GET', f'{domain}/api/care-v1/home/welcome', 'home/welcome (应删除->404)'),
    ('GET', f'{domain}/api/care-v1/home/proactive-cards', 'proactive-cards (应删除->404)'),
    ('GET', f'{domain}/api/care-v1/sos/events', 'sos/events (应删除->404)'),
    ('GET', f'{domain}/api/care-v1/sos/keywords', 'sos/keywords (应删除->404)'),
    ('GET', f'{domain}/care-home', 'care-home (应跳转)'),
    ('GET', f'{domain}/care-ai-home', 'care-ai-home'),
    ('GET', f'{domain}/api/health', 'API健康检查'),
]

for method, url, desc in tests:
    try:
        r = requests.request(method, url, allow_redirects=False, timeout=10, verify=False)
        redirect = ''
        if r.status_code in (301, 302, 307, 308):
            redirect = f' -> {r.headers.get("Location", "")}'
        print(f'{r.status_code:>4} | {desc}{redirect}')
    except Exception as e:
        print(f' ERR | {desc}: {e}')
