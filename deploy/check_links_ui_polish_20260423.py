"""Link check for UI polish PRD (2026-04-23)."""
from __future__ import annotations

import sys
import urllib.request
import urllib.error

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

LINKS = [
    # H5 pages
    ('H5 / Home', f'{BASE}/'),
    ('H5 / AI ', f'{BASE}/ai'),
    ('H5 / My Addresses', f'{BASE}/my-addresses'),
    ('H5 / Profile', f'{BASE}/profile'),
    ('H5 / Home Tab', f'{BASE}/home'),
    # Admin
    ('Admin Login', f'{BASE}/admin/login'),
    # Backend API
    ('API / Health', f'{BASE}/api/health'),
    ('API / Docs', f'{BASE}/api/docs'),
    ('API / OpenAPI', f'{BASE}/api/openapi.json'),
]

ACCEPT = {200, 301, 302, 303, 307, 308, 401, 403}


def check(name: str, url: str) -> bool:
    req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'curl/7.88'})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # noqa: BLE001
        print(f'[FAIL] {name:26s} {url}  ERR={e}')
        return False
    ok = code in ACCEPT
    tag = 'OK  ' if ok else 'FAIL'
    print(f'[{tag}] {name:26s} {url}  -> {code}')
    return ok


def main() -> int:
    total = len(LINKS)
    passed = 0
    for name, url in LINKS:
        if check(name, url):
            passed += 1
    print(f'\n==== SUMMARY: {passed}/{total} passed ====')
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
