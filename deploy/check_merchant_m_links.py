"""链接可达性检查：商家端移动端 H5"""
from __future__ import annotations
import urllib.request
import urllib.error
import ssl
import json
import sys

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

PATHS = [
    '/merchant/m/login',
    '/merchant/m/dashboard',
    '/merchant/m/orders',
    '/merchant/m/verify',
    '/merchant/m/reports',
    '/merchant/m/settlement',
    '/merchant/m/store-settings',
    '/merchant/m/staff',
    '/merchant/m/me',
    '/merchant/m/select-store',
    '/merchant/m/invoice',
    '/merchant/m/downloads',
    '/merchant/m/finance',
    '/merchant/m/messages',
    '/merchant/m/',
]

UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) '
      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1')


def check(url: str) -> tuple[int, str]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        status = resp.status
        body = resp.read(2000).decode('utf-8', errors='replace')
        return status, body[:200]
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read(500).decode('utf-8', errors='replace')
        except Exception:
            pass
        return e.code, body[:200]
    except Exception as e:
        return 0, f'ERR: {e}'


def main() -> int:
    fail = 0
    results = []
    for p in PATHS:
        url = BASE + p
        status, snippet = check(url)
        ok = status in (200, 307, 308)
        if not ok:
            fail += 1
        print(f'{"✅" if ok else "❌"} [{status}] {url}')
        if not ok:
            print(f'   -> {snippet!r}')
        results.append({'path': p, 'url': url, 'status': status, 'ok': ok})

    print('\nSummary: %d/%d passed' % (len(PATHS) - fail, len(PATHS)))

    with open('deploy/link_check_merchant_m.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
