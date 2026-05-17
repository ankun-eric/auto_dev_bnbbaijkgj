"""探测小程序 zip 的有效访问 URL 路径"""
import urllib.request

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'
FILE = 'miniprogram_20260517_110717_f4fc_timezone_global.zip'

candidates = [
    f'{BASE}/{FILE}',
    f'{BASE}/static/{FILE}',
    f'{BASE}/files/{FILE}',
    f'{BASE}/miniprogram/{FILE}',
    f'{BASE}/downloads/{FILE}',
    f'{BASE}/assets/{FILE}',
    f'{BASE}/dl/{FILE}',
]

for url in candidates:
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f'[OK {resp.status}] {url}  size={resp.headers.get("Content-Length")}')
    except Exception as e:
        print(f'[--] {url}  {e}')
