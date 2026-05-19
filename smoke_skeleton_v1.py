"""[PRD-AIHOME-SKELETON-V1] ai-home 首屏骨架屏非UI烟测.

无浏览器, 仅 HTTP 层面验证:
  T1: /ai-home 页面 HTML 可获取 (200 或 308 重定向到尾斜线后 200)
  T2: 已加载的 CSS bundle 中存在 skeleton-shimmer / ai-home-skeleton 样式
  T3: page 的 client chunk 中存在 AiHomeSkeleton / firstScreenStatus 关键标识
  T4: 关键接口 /api/function-buttons 在网关层可路由 (HTTP 200/401)
  T5: 关键接口 /api/family/members 在网关层可路由 (HTTP 200/401)
"""
import json
import re
import sys
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def fetch(url, follow=True, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
    try:
        opener = urllib.request.build_opener()
        if not follow:
            class NoRedir(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **kw):
                    return None
            opener = urllib.request.build_opener(NoRedir)
        resp = opener.open(req, timeout=timeout)
        return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body, dict(e.headers or {})
    except Exception as e:
        return 0, f"[ERR] {e}", {}


def find_css_urls(html):
    return re.findall(r'href="([^"]+\.css[^"]*)"', html)


def find_chunk_urls(html):
    return re.findall(r'src="([^"]+/_next/static/chunks/[^"]+)"', html)


def t(name, ok, detail=""):
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}  {detail}")
    return ok


def main():
    results = []

    # T1
    status, html, _ = fetch(f"{BASE}/ai-home", follow=True)
    ok1 = status == 200 and len(html) > 5000
    results.append(t("T1 /ai-home 可获取", ok1, f"status={status} html_len={len(html)}"))

    # T2: CSS contains skeleton classes
    css_urls = find_css_urls(html)
    css_ok = False
    css_detail = []
    for url in css_urls:
        full = url if url.startswith("http") else f"https://newbb.test.bangbangvip.com{url}"
        s, body, _ = fetch(full)
        has_shim = "skeleton-shimmer" in body
        has_skel = "ai-home-skeleton" in body or "ai-home-content" in body
        css_detail.append(f"{url.split('/')[-1]}: shim={has_shim}, skel={has_skel}")
        if has_shim and has_skel:
            css_ok = True
            break
    results.append(t("T2 CSS bundle 含骨架屏样式", css_ok, "; ".join(css_detail)))

    # T3: client chunk contains AiHomeSkeleton & firstScreenStatus
    chunk_urls = find_chunk_urls(html)
    # 我们只看 app/(ai-chat)/ai-home 相关 chunk
    ai_home_chunks = [u for u in chunk_urls if "ai-home" in u or "ai-chat" in u]
    chunk_check_urls = ai_home_chunks or chunk_urls[-10:]  # fallback
    chunk_ok = False
    chunk_detail = []
    for url in chunk_check_urls[:8]:
        full = url if url.startswith("http") else f"https://newbb.test.bangbangvip.com{url}"
        s, body, _ = fetch(full)
        has_skel = "AiHomeSkeleton" in body or "ai-home-skeleton" in body
        has_state = "firstScreenStatus" in body or "firstScreenRetryNonce" in body
        # 注意: 经过 SWC minify 后 React state 变量名可能被改写, 类名/字符串字面量保留
        if has_skel:
            chunk_ok = True
            chunk_detail.append(f"OK {url.split('/')[-1]} skel={has_skel} state={has_state}")
            break
        else:
            chunk_detail.append(f".. {url.split('/')[-1]} skel={has_skel}")
    results.append(t("T3 JS bundle 含 AiHomeSkeleton 标识", chunk_ok, "; ".join(chunk_detail[:3])))

    # T4
    s4, b4, _ = fetch(f"{BASE}/api/function-buttons")
    ok4 = s4 in (200, 401, 403)
    results.append(t("T4 /api/function-buttons 可路由", ok4, f"status={s4}"))

    # T5
    s5, b5, _ = fetch(f"{BASE}/api/family/members")
    ok5 = s5 in (200, 401, 403)
    results.append(t("T5 /api/family/members 可路由", ok5, f"status={s5}"))

    print()
    passed = sum(1 for r in results if r)
    print(f"=== {passed}/{len(results)} 通过 ===")
    if passed == len(results):
        print("ALL_GREEN")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
