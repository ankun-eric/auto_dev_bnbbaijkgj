"""根据找到的实际路径，探测正确的下载 URL"""
import urllib.request

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'
# 上次成功的文件
KNOWN_FILE = 'miniprogram_20260517_023326_bug_report_interpret.zip'

candidates = [
    f'{BASE}/miniprogram/{KNOWN_FILE}',
    f'{BASE}/{KNOWN_FILE}',
    f'{BASE}/static/miniprogram/{KNOWN_FILE}',
    f'{BASE}/downloads/{KNOWN_FILE}',
    f'{BASE}/miniprogram_releases/{KNOWN_FILE}',
]

for url in candidates:
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f'[OK {resp.status}] {url}  size={resp.headers.get("Content-Length")}')
    except Exception as e:
        print(f'[--] {url}  {e}')
