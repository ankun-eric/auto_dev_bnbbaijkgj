"""[BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 部署后冒烟测试"""
import urllib.request, ssl, sys
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
BASE = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'
URLS = [
    f'{BASE}/',
    f'{BASE}/health-profile',
    f'{BASE}/health-metric/blood_pressure',
    f'{BASE}/admin/',
    f'{BASE}/api/health',
]
fail = 0
for u in URLS:
    try:
        req = urllib.request.Request(u, headers={'User-Agent':'smoke'})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            body = r.read(2048)
            print(f'[{r.status}] {u} ({len(body)} bytes head)')
    except Exception as e:
        print(f'[ERR] {u}: {e}')
        fail += 1
print(f'\nfail count: {fail}')
sys.exit(fail)
