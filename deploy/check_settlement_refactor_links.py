"""对账单管理重构 链接可达性验证脚本。"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
import ssl

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

# admin-web 在 nginx 层被挂到 /admin/ 前缀下（basePath=/autodev/<id>/admin）
# 根 URL 直接访问到 h5-web（前端门户），故 admin 页面实际路径是 /admin/<route>/。
ADMIN_BASE = f'{BASE}/admin'

# (url, expected_ok_codes_str, kind)
TARGETS = [
    (f'{BASE}/', '200,302,301,404,308', 'frontend-h5-root'),
    (f'{ADMIN_BASE}/admin-settlements/', '200,302,301,307,308', 'frontend-admin'),
    (f'{ADMIN_BASE}/admin-settlements', '200,302,301,307,308', 'frontend-admin'),
    (f'{ADMIN_BASE}/login/', '200,302,301,307,308', 'frontend-admin'),
    (f'{BASE}/login', '200,302,301,307,308', 'frontend-h5'),
    (f'{BASE}/api/health', '200,401,404,405,422', 'api'),
    (f'{BASE}/api/docs', '200,401,404,307,308', 'api'),
    (f'{BASE}/api/admin/settlements?page=1&page_size=20', '200,401,403,422', 'api'),
    (f'{BASE}/api/admin/settlements/merchant-options', '200,401,403,422', 'api'),
    (f'{BASE}/api/admin/settlements/store-options', '200,401,403,422', 'api'),
    (f'{BASE}/api/admin/settlements/1', '200,401,403,404,422', 'api'),
]


def probe(url: str, timeout: float = 15.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'deploy-linkcheck/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, ''
    except urllib.error.HTTPError as e:
        return e.code, e.reason or ''
    except urllib.error.URLError as e:
        return 0, f'URLError: {e.reason}'
    except Exception as e:  # noqa: BLE001
        return 0, f'{type(e).__name__}: {e}'


def main() -> int:
    rows = []
    all_ok = True
    for url, ok_codes, kind in TARGETS:
        ok_set = {int(x) for x in ok_codes.split(',')}
        code, note = probe(url)
        ok = code in ok_set
        if not ok:
            all_ok = False
        rows.append({
            'url': url,
            'kind': kind,
            'status': code,
            'note': note,
            'ok_expected': ok_codes,
            'reachable': ok,
        })
        tag = 'OK' if ok else 'FAIL'
        print(f'[{tag}] {code:>3}  {kind:<8}  {url}  (accept: {ok_codes}) {note}')

    print()
    total = len(rows)
    ok_count = sum(1 for r in rows if r['reachable'])
    print(f'summary: {ok_count}/{total} reachable')

    with open('deploy/link_check_settlement_refactor.json', 'w', encoding='utf-8') as f:
        json.dump({
            'base': BASE,
            'ok_count': ok_count,
            'total': total,
            'all_ok': all_ok,
            'results': rows,
        }, f, ensure_ascii=False, indent=2)

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
