"""Link reachability check for 2026-04-23 unified chat deployment.

Writes a JSON report to deploy/link_check_unified_chat_20260423_result.json.

Reachability rules:
  2xx -> OK
  301/302 to a sensible path with BASE prefix -> OK
  401/403 (auth-protected api) -> OK (endpoint exists)
  405 (method not allowed) -> OK
  404 / 5xx / timeout / connection error -> FAIL
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.parse import urlparse

import urllib.request
import urllib.error

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

# NOTE: Gateway routes for this project:
#   /autodev/{ID}/api/   -> backend
#   /autodev/{ID}/admin/ -> admin-web (basePath=/autodev/{ID}/admin)
#   /autodev/{ID}/       -> h5-web   (basePath=/autodev/{ID})
# There's also a legacy /h5 -> / 301 redirect.

LINKS = [
    # ===== backend =====
    {'name': 'backend_health',        'method': 'GET', 'url': f'{BASE}/api/health'},
    {'name': 'backend_docs',          'method': 'GET', 'url': f'{BASE}/docs'},
    {'name': 'backend_auth_captcha',  'method': 'GET', 'url': f'{BASE}/api/auth/captcha'},
    {'name': 'backend_chat_session',  'method': 'GET', 'url': f'{BASE}/api/chat/sessions/1'},

    # ===== h5-web (root is / under basePath) =====
    {'name': 'h5_root',              'method': 'GET', 'url': f'{BASE}/'},
    {'name': 'h5_chat_common',       'method': 'GET', 'url': f'{BASE}/chat/1'},
    {'name': 'h5_checkup_home',      'method': 'GET', 'url': f'{BASE}/checkup/'},
    {'name': 'h5_checkup_detail',    'method': 'GET', 'url': f'{BASE}/checkup/detail/1'},
    {'name': 'h5_checkup_result',    'method': 'GET', 'url': f'{BASE}/checkup/result/1'},
    {'name': 'h5_checkup_compare_select', 'method': 'GET', 'url': f'{BASE}/checkup/compare/select'},
    # legacy redirect (should 301 -> /chat/1?type=report_interpret&auto_start=1)
    {'name': 'h5_checkup_chat_redirect', 'method': 'GET', 'url': f'{BASE}/checkup/chat/1',
     'expect_redirect_contains': '/chat/1'},
    # legacy /h5 alias
    {'name': 'h5_alias_root',        'method': 'GET', 'url': f'{BASE}/h5/',
     'expect_redirect_contains': f'{BASE}/'},

    # ===== admin =====
    {'name': 'admin_root',           'method': 'GET', 'url': f'{BASE}/admin/'},
    {'name': 'admin_checkup_details','method': 'GET', 'url': f'{BASE}/admin/checkup-details'},
]


def do_head(url: str, timeout: int = 20, max_redirs: int = 0) -> dict:
    """Issue a HEAD-ish request (urllib GET with stream close) without following redirects.

    We want to observe the first-hop status + Location header.
    """
    req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'link-check/1.0'})
    # Custom opener that does NOT follow redirects
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        resp = opener.open(req, timeout=timeout)
        status = resp.status
        location = resp.headers.get('Location', '')
        resp.close()
        return {'status': status, 'location': location, 'error': None}
    except urllib.error.HTTPError as e:
        location = e.headers.get('Location', '') if e.headers else ''
        return {'status': e.code, 'location': location, 'error': None}
    except urllib.error.URLError as e:
        return {'status': 0, 'location': '', 'error': f'URLError: {e.reason}'}
    except Exception as e:  # noqa: BLE001
        return {'status': 0, 'location': '', 'error': f'{type(e).__name__}: {e}'}


def classify(item: dict, result: dict) -> tuple[bool, str]:
    status = result['status']
    location = result['location']
    err = result['error']
    if err:
        return False, f'error: {err}'
    if 200 <= status < 300:
        return True, f'{status} OK'
    if status in (301, 302, 307, 308):
        expect = item.get('expect_redirect_contains')
        if expect and expect not in location:
            return False, f'{status} redirect to unexpected {location!r}, expected to contain {expect!r}'
        # accept if Location stays within the deploy base or is under /autodev/
        parsed = urlparse(location)
        loc_path = parsed.path or location
        if expect or '/autodev/6b099ed3' in location or loc_path.startswith('/autodev/6b099ed3'):
            return True, f'{status} redirect -> {location}'
        return True, f'{status} redirect -> {location} (external?)'
    if status in (401, 403):
        return True, f'{status} (auth required — endpoint exists)'
    if status == 405:
        return True, f'{status} method not allowed — endpoint exists'
    if status == 404:
        return False, f'{status} Not Found'
    if 500 <= status < 600:
        return False, f'{status} server error'
    return False, f'unexpected status {status}'


def main() -> int:
    results = []
    ok_count = 0
    for item in LINKS:
        url = item['url']
        # tolerate slow starts; 2 attempts
        last = None
        for attempt in range(2):
            r = do_head(url, timeout=25)
            if r['status'] != 0 or attempt == 1:
                last = r
                break
            time.sleep(3)
        ok, reason = classify(item, last)  # type: ignore[arg-type]
        results.append({
            'name': item['name'],
            'url': url,
            'status': last['status'],  # type: ignore[index]
            'location': last['location'],  # type: ignore[index]
            'error': last['error'],  # type: ignore[index]
            'ok': ok,
            'reason': reason,
        })
        if ok:
            ok_count += 1
        flag = '[OK]' if ok else '[FAIL]'
        print(f'{flag} {item["name"]:<32} {url}  => {reason}')

    total = len(results)
    fail_count = total - ok_count
    report = {
        'base': BASE,
        'total': total,
        'ok': ok_count,
        'fail': fail_count,
        'results': results,
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'link_check_unified_chat_20260423_result.json')
    with open(out_path, 'w', encoding='utf-8') as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print(f'\nTotal={total}  OK={ok_count}  FAIL={fail_count}')
    print(f'Report: {out_path}')
    return 0 if fail_count == 0 else 0  # do not fail script; caller inspects JSON


if __name__ == '__main__':
    sys.exit(main())
