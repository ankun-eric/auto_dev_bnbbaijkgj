import urllib.request
import sys

ZIP = 'miniprogram_home3bugs_20260421_034031_86c1.zip'
BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

urls = [
    f'{BASE}/static/downloads/{ZIP}',
    f'{BASE}/static/downloads/miniprogram_latest.zip',
    f'{BASE}/downloads/{ZIP}',
]

all_ok = True
for u in urls:
    try:
        req = urllib.request.Request(u, method='HEAD')
        with urllib.request.urlopen(req, timeout=20) as r:
            cl = r.headers.get('Content-Length')
            print(f'{r.status}  Content-Length={cl}  {u}')
            if r.status != 200:
                all_ok = False
    except Exception as e:
        print(f'ERR  {u}  -> {e}')
        all_ok = False

sys.exit(0 if all_ok else 1)
