"""Verify h5 + backend critical URLs after deploy."""
import urllib.request
import ssl
import time

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

URLS = [
    ('H5 root', f'{BASE}/'),
    ('H5 /drug', f'{BASE}/drug'),
    ('H5 /chat/1', f'{BASE}/chat/1'),
    ('H5 /chat (list)', f'{BASE}/chat'),
    ('H5 /home', f'{BASE}/home'),
    ('H5 /health', f'{BASE}/health'),
    ('H5 /login', f'{BASE}/login'),
    ('Backend health', f'{BASE}/api/health'),
    ('Backend docs', f'{BASE}/api/docs'),
    ('Admin root', f'{BASE}/admin/'),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def check(label, url):
    req = urllib.request.Request(url, headers={'User-Agent': 'verify-bot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            return resp.status, len(resp.read()[:200])
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception as e:
        return f'ERR:{type(e).__name__}:{e}', 0

print(f"{'Status':<10}{'Size':<8}Label / URL")
print('-' * 100)

results = []
for label, url in URLS:
    # 2 retries
    last = None
    for attempt in range(3):
        status, size = check(label, url)
        last = (status, size)
        if isinstance(status, int):
            break
        time.sleep(2)
    status, size = last
    ok = isinstance(status, int) and status not in (500, 502, 503, 504)
    flag = 'OK ' if ok else 'BAD'
    results.append((label, url, status, ok))
    print(f"{str(status):<10}{size:<8}[{flag}] {label}  {url}")

print('-' * 100)
bad = [r for r in results if not r[3]]
print(f"\nTotal: {len(results)}, Bad: {len(bad)}")
if bad:
    print("BAD URLS:")
    for r in bad:
        print(f"  - {r[2]}  {r[1]}")
    raise SystemExit(1)
print("ALL REACHABLE")
