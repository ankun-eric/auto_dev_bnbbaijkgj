"""Verify multi-image fix endpoints are reachable (2026-04-23)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

ENDPOINTS = [
    # 前端
    ('GET', f'{BASE}/', 'H5 homepage'),
    ('GET', f'{BASE}/login', 'H5 login'),
    ('GET', f'{BASE}/checkup', 'H5 checkup entry'),
    # 后端健康与 API
    ('GET', f'{BASE}/api/health', 'backend health'),
    # 后端未认证接口返回 401/422 也算可达
    ('GET', f'{BASE}/api/checkup/reports/1', 'checkup get_report (expect 401/404)'),
    ('GET', f'{BASE}/api/chat/sessions/1', 'chat session detail (expect 401/404)'),
]


def check(method: str, url: str, label: str) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=20) as r:
            return True, f'{label}: HTTP {r.status}'
    except urllib.error.HTTPError as e:
        # 4xx 也视为后端可达
        ok = e.code in (400, 401, 403, 404, 405, 422)
        return ok, f'{label}: HTTP {e.code}'
    except Exception as e:  # noqa: BLE001
        return False, f'{label}: ERROR {e}'


def main() -> int:
    print(f'[verify] BASE={BASE}')
    total = len(ENDPOINTS)
    fail = 0
    for method, url, label in ENDPOINTS:
        ok, msg = check(method, url, label)
        print(f'  [{ "OK" if ok else "FAIL" }] {msg}  {url}')
        if not ok:
            fail += 1
    print(f'[verify] total={total} fail={fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
