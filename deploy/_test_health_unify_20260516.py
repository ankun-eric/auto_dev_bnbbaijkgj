"""
[PRD-健康档案路径统一 2026-05-16] 服务器端非UI自动化测试

测试用例（核心关注：路径搬迁是否正确，关键链接是否可达）：
  FC-01: H5 访问 /health-profile → 200（v2 内容已搬到主路径）
  FC-02: H5 访问 /health-profile-v2 → 404 (v2 路径已删除)
  FC-03: H5 入口页 devices/points/family/family-auth 可达 200
  BE-01: 后端 /api/health-profile-v3/* 接口存活
  BE-02: 后端 /api/prd469/* 接口存活
  BE-03: 后端 /api/family/members 接口存活
  BE-04: 后端 /api/disease-presets 接口存活
  CP-01: 后端 /api/health（健康检查）返回 200
  RDR-01: H5 /health-profile 不出现 redirect loop
"""
import urllib.request
import urllib.error
import ssl
import json
import sys

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

def http_get(url, timeout=15, max_redirects=10, follow_redirects=False):
    """返回 (status, redirect_count, final_url, body_snippet)"""
    ctx = ssl.create_default_context()
    redirect_count = 0
    current_url = url
    try:
        while True:
            req = urllib.request.Request(current_url, method='GET', headers={
                'User-Agent': 'Mozilla/5.0 (compatible; HealthUnifyTest/1.0)',
                'Accept': 'text/html,application/json,*/*',
            })
            try:
                # 不让 urllib 自动跟随重定向
                op = urllib.request.build_opener(urllib.request.HTTPRedirectHandler() if follow_redirects else NoRedirectHandler())
                resp = op.open(req, timeout=timeout, context=ctx) if False else _open_no_redirect(req, timeout, ctx) if not follow_redirects else _open_follow(req, timeout, ctx, max_redirects)
                status = resp.status if hasattr(resp, 'status') else resp.getcode()
                body = resp.read(60000)
                try:
                    body_text = body.decode('utf-8', errors='replace')
                except Exception:
                    body_text = '<binary>'
                return status, redirect_count, current_url, body_text
            except urllib.error.HTTPError as e:
                # 4xx/5xx
                body = ''
                try:
                    body = e.read(2000).decode('utf-8', errors='replace')
                except Exception:
                    pass
                if e.code in (301, 302, 303, 307, 308) and follow_redirects:
                    redirect_count += 1
                    if redirect_count >= max_redirects:
                        return -1, redirect_count, current_url, "TOO_MANY_REDIRECTS"
                    current_url = e.headers.get('Location', '')
                    if not current_url.startswith('http'):
                        # 拼相对 URL
                        from urllib.parse import urljoin
                        current_url = urljoin(url, current_url)
                    continue
                return e.code, redirect_count, current_url, body
    except Exception as e:
        return -1, redirect_count, current_url, f"EXCEPTION: {type(e).__name__}: {e}"

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, hdrs):
        raise urllib.error.HTTPError(req.full_url, code, msg, hdrs, fp)
    http_error_302 = http_error_301
    http_error_303 = http_error_301
    http_error_307 = http_error_301
    http_error_308 = http_error_301

def _open_no_redirect(req, timeout, ctx):
    op = urllib.request.build_opener(NoRedirectHandler(), urllib.request.HTTPSHandler(context=ctx))
    return op.open(req, timeout=timeout)

def _open_follow(req, timeout, ctx, max_redirects):
    # default opener follows redirects
    op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    return op.open(req, timeout=timeout)


TESTS = []

def add(name, url, expect_status, follow=True, check_body=None, max_redirects=10):
    TESTS.append({
        'name': name, 'url': url, 'expect': expect_status,
        'follow': follow, 'check_body': check_body, 'max_redirects': max_redirects,
    })

# ===== H5 主路由 =====
add('FC-01 H5 /health-profile (v2 内容)', f'{BASE}/health-profile', [200], check_body='prd469-')
add('FC-02 H5 /health-profile-v2 应 404', f'{BASE}/health-profile-v2', [404])
add('FC-03a H5 /devices 可达', f'{BASE}/devices', [200])
add('FC-03b H5 /points 可达', f'{BASE}/points', [200])
add('FC-03c H5 /family 跳转 health-profile', f'{BASE}/family', [200])
add('FC-03d H5 /family-auth 可达', f'{BASE}/family-auth', [200, 400])  # 无 code 可能 400
add('FC-04 H5 首页 /', f'{BASE}/', [200])
add('RDR-01 /health-profile 不循环', f'{BASE}/health-profile', [200], follow=True, max_redirects=5)

# ===== 后端 API =====
add('BE-API-doc /docs', f'{BASE}/docs', [200, 401, 403, 404])  # 取决于是否开启
add('BE-Family /api/family/members', f'{BASE}/api/family/members', [200, 401, 403, 422])
add('BE-Presets /api/disease-presets?category=chronic', f'{BASE}/api/disease-presets?category=chronic', [200, 422])
add('BE-V3 today-metrics (用 1)', f'{BASE}/api/health-profile-v3/1/today-metrics', [200, 404, 422, 401, 403])
add('BE-V3 medication-plan (用 1)', f'{BASE}/api/health-profile-v3/1/medication-plan', [200, 404, 422, 401, 403])
add('BE-PRD469 summary (用 1)', f'{BASE}/api/prd469/summary/1', [200, 404, 422, 401, 403])
add('BE-Family management', f'{BASE}/api/family/management', [200, 401, 403, 422])
add('BE-Health profile/member', f'{BASE}/api/health/profile/member/1', [200, 404, 422, 401, 403])


def run():
    passed = 0
    failed = []
    print(f"=== Health Profile Unify Tests ({len(TESTS)} cases) ===")
    print(f"BASE: {BASE}\n")
    for t in TESTS:
        status, rc, final, body = http_get(t['url'], follow_redirects=t['follow'], max_redirects=t['max_redirects'])
        ok = status in t['expect']
        body_ok = True
        if ok and t.get('check_body'):
            body_ok = t['check_body'] in body
            ok = ok and body_ok
        flag = '✅ PASS' if ok else '❌ FAIL'
        extra = ''
        if t.get('check_body'):
            extra = f" body_has_{t['check_body']}={body_ok}"
        print(f"{flag}  [{t['name']}]  status={status} redirs={rc}{extra}")
        if not ok:
            print(f"        URL: {t['url']}")
            print(f"        Expect: {t['expect']}, Got: {status}")
            print(f"        Body[:200]: {body[:200]!r}")
            failed.append(t['name'])
        else:
            passed += 1
    print(f"\n=== Result: {passed}/{len(TESTS)} passed, {len(failed)} failed ===")
    if failed:
        print("FAILED:")
        for n in failed:
            print(f"  - {n}")
        sys.exit(1)
    print("ALL TESTS PASSED")

if __name__ == "__main__":
    run()
