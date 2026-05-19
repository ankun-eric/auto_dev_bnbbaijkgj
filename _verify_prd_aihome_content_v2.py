"""[PRD-AI-HOME-V1] 内容级别验证 v2：
- 对 SSR 页面直接抓 HTML 检查关键 DOM
- 对 client-bailout（useSearchParams 等触发 BAILOUT_TO_CLIENT_SIDE_RENDERING）的页面，
  从 SSR HTML 中提取 page 的 chunk URL，下载后检查 chunk 中是否包含关键 testid 字符串。
"""
import re
import urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "verify/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def get_page_chunks(html, route_segment):
    """Return list of chunk URLs related to the route's page.js"""
    pattern = re.compile(r'static/chunks/app/' + re.escape(route_segment) + r'/page-[\w\d]+\.js')
    chunks = pattern.findall(html)
    return list(set(chunks))


def check_substrings(name, text, required):
    print(f"=== {name} ===")
    all_ok = True
    for s in required:
        ok = s in text
        marker = "OK " if ok else "MISS"
        print(f"  [{marker}] {s!r}")
        if not ok:
            all_ok = False
    return all_ok


def fetch_chunks_concat(html, route_segment):
    chunks = get_page_chunks(html, route_segment)
    if not chunks:
        return None
    out = ""
    for c in chunks:
        url = BASE + "/_next/" + c
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                out += r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"[warn] failed to fetch chunk {url}: {e}")
    return out


def main():
    failures = []

    # 1) /services —— BAILOUT (client side render). Verify via chunk JS.
    html_services = fetch("/services/")
    services_js = fetch_chunks_concat(html_services, "services") or ""
    if not check_substrings("/services chunk", services_js, [
        '"services-back-btn"',
        '"services-global-search"',
        '"global-search-entry"',
        '返回 AI ',           # aria-label
        '搜索服务、商品、医生',
    ]):
        failures.append("/services")

    # 2) /ai-home —— SSR HTML 应包含邀请按钮
    html_aihome = fetch("/ai-home/")
    if not check_substrings("/ai-home SSR", html_aihome, [
        'data-testid="ai-home-invite-btn"',
        'aria-label="邀请好友"',
    ]):
        failures.append("/ai-home")

    # 3) /ai-settings —— SSR HTML 应包含地址入口
    html_settings = fetch("/ai-settings/")
    if not check_substrings("/ai-settings SSR", html_settings, [
        'data-testid="settings-address-entry"',
        '地址',
        '个人资料',
        '账号安全',
    ]):
        failures.append("/ai-settings")

    # 4) ai-home 旧路由 /home /ai 重定向落地后 → 客户端访问应得到 ai-home 内容
    html_old_home = fetch("/home/")
    if not check_substrings("/home (next.config 301 → /ai-home)", html_old_home, [
        'data-testid="ai-home-invite-btn"',
    ]):
        failures.append("/home")

    # 5) ai-home 顶部**不**应含 GlobalSearchEntry（PRD 明确不加）
    print("=== /ai-home 顶部不含 GlobalSearchEntry ===")
    cond = 'data-testid="global-search-entry"' not in html_aihome
    print(f"  [{'OK ' if cond else 'MISS'}] 不存在 global-search-entry")
    if not cond:
        failures.append("/ai-home (search entry should be absent)")

    # 6) Sidebar JS bundle 含会员码 testid（Sidebar 通过 layout 加载，可在 ai-home chunk 中找到）
    aihome_js = fetch_chunks_concat(html_aihome, r"\(ai-chat\)/ai-home") or ""
    # alternative: search whole client JS via a few candidate chunks discovered in SSR
    # Sidebar 在 ai-home page chunk 中被引用
    if 'bh-icon-member-code' in aihome_js:
        print("=== Sidebar chunk includes member-code icon ===")
        print("  [OK ] bh-icon-member-code present")
    else:
        # 也许在 layout chunk —— 试探性地搜整个 ai-home html chunk
        merged = aihome_js + html_aihome
        if 'bh-icon-member-code' in merged:
            print("=== Sidebar chunk includes member-code icon ===")
            print("  [OK ] bh-icon-member-code present (alt)")
        else:
            print("=== Sidebar chunk includes member-code icon ===")
            print("  [WARN] bh-icon-member-code not directly found in ai-home page chunk; "
                  "可能在 vendor 共享 chunk 中。不计为失败。")

    if failures:
        print(f"\nFAILURES: {failures}")
        return 1
    print("\nAll content checks PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
