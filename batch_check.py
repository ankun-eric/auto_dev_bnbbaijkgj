"""Batch URL accessibility checker for noob-test-skill."""
import http.client
import urllib.parse
import ssl
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

ctx = ssl.create_default_context()

def check_url(url, max_redirects=10):
    """Check a single URL, following redirects manually to count them."""
    result = {"url": url, "status": None, "redirect_count": 0, "final_url": url, "error": None, "ok": False}
    current_url = url
    for i in range(max_redirects + 1):
        parsed = urllib.parse.urlparse(current_url)
        conn = http.client.HTTPSConnection(parsed.hostname, timeout=15, context=ctx)
        try:
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
            conn.request("GET", path, headers={"Host": parsed.hostname, "User-Agent": "noob-test-skill/1.0"})
            resp = conn.getresponse()
            result["status"] = resp.status
            result["final_url"] = current_url
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location", "")
                if location:
                    result["redirect_count"] += 1
                    if location.startswith("/"):
                        current_url = f"https://{parsed.hostname}{location}"
                    elif location.startswith("http"):
                        current_url = location
                    else:
                        current_url = f"https://{parsed.hostname}/{location}"
                    conn.close()
                    continue
            # Not a redirect - check status
            result["ok"] = resp.status in (200, 201, 202, 203, 204, 304, 405)
            conn.close()
            return result
        except Exception as e:
            result["error"] = str(e)
            try: conn.close()
            except: pass
            return result
    result["error"] = f"Too many redirects ({max_redirects})"
    return result

# Frontend pages to check
frontend_pages = [
    "/",
    "/ai-home/medication-reminder",
    "/ai-home/medication-reminder/history",
    "/ai-home",
    "/login",
    "/health-profile",
    "/health-dashboard",
    "/health-plan",
    "/health-reminders",
    "/health-alerts",
    "/health-guide",
    "/messages",
    "/settings",
    "/search",
    "/products",
    "/services",
    "/points",
    "/my-favorites",
    "/my-coupons",
    "/my-addresses",
    "/member-card",
    "/member-center",
    "/landing",
    "/news",
    "/articles",
    "/checkup",
    "/drug",
    "/tcm",
    "/scan",
    "/glucose",
    "/brain-game",
    "/home-safety",
    "/devices",
    "/medical-records",
    "/care-ai-home",
    "/appointment",
    "/cards",
    "/merchant/login",
    "/invite",
    "/refund-list",
    "/orders",
    "/report-history",
    "/symptom",
    "/experts",
    "/coupon-center",
    "/customer-service",
    "/feedback",
    "/ai-settings",
    "/account-security",
    "/chat-history",
    "/family-guardian-list",
    "/family-invite",
    "/family-alert",
    "/digital-human-call",
    "/health-plan/checkin",
    "/health-plan/custom",
    "/health-plan/edit",
    "/health-plan/statistics",
    "/health-plan/result",
    "/ai-home/medication-plans",
    "/ai-home/medication-plans/new",
    "/checkup/compare",
    "/checkup/trend",
    "/tcm/archive",
    "/glucose/records",
    "/medical-records/all",
    "/health-profile/archive-list",
    "/health-profile/my-guardians",
    "/health-profile/i-guard",
    "/cards/wallet",
    "/care-ai-home/info-card",
    "/care-ai-home/sos",
    "/care-ai-home/today-health",
    "/share/location",
]

# Backend APIs to check
backend_apis = [
    "/api/health",
    "/api/medication/calendar?year=2026&month=6",
    "/api/medication/records?date=2026-06-07",
    "/api/medication/today",
    "/api/medication-reminder/plans",
    "/api/medication-reminder/today",
    "/api/medication-reminder/badge",
    "/api/medication-plans/today",
    "/api/medication-plans/hero-count",
    "/api/medication-plans/summary",
    "/api/medication-check-in",
    "/api/medication-library/suggest?q=test",
    "/api/auth/login",
    "/api/users/profile",
    "/api/health-profile",
    "/api/health-plan",
    "/api/chat/sessions",
    "/api/ai-home/config",
    "/api/bottom-nav",
    "/api/home-config",
    "/api/family/members",
    "/api/points/balance",
    "/api/orders/unified",
    "/api/products",
    "/api/services",
    "/api/coupons",
    "/api/cards",
    "/api/appointment/forms",
    "/api/notifications",
    "/api/messages/unread",
    "/api/addresses",
    "/api/feedback",
    "/api/search",
    "/api/upload/url",
    "/api/city/list",
    "/api/experts",
    "/api/tcm/constitution",
    "/api/health-dashboard",
    "/api/health-metric",
    "/api/glucose",
    "/api/brain-game",
    "/api/home-safety",
    "/api/devices",
    "/api/ocr",
    "/api/tts",
    "/api/scan",
    "/api/report",
    "/api/checkup",
    "/api/drug/identify",
    "/api/merchant/stores",
    "/api/ai-call",
    "/api/health-self-check",
    "/api/questionnaire",
    "/api/health-archive",
    "/api/maps",
    "/api/sms/send",
    "/api/email-notify",
    "/api/wechat-push",
    "/api/knowledge",
    "/api/cos/token",
    "/api/constitution",
    "/api/drug-chat",
    "/api/chat-share",
    "/api/consultant-profile",
    "/api/analytics/event",
    "/api/frontend-log",
    "/api/payment-methods",
    "/api/membership",
    "/api/member-center",
    "/api/common/time-slots",
    "/api/system/time",
    "/api/login-ui-config",
    "/api/video-consult-config",
    "/api/account-security",
    "/api/ai-center",
    "/api/function-buttons",
    "/api/prompt-templates",
    "/api/prompt-type-config",
    "/api/report-interpret",
    "/api/drug-identify-share",
    "/api/favorites",
    "/api/member-qr",
    "/api/unified-orders",
    "/api/app-settings",
    "/api/tcm-config",
    "/api/themes",
    "/api/notice",
    "/api/plan",
    "/api/referral",
    "/api/h5-checkout",
    "/api/payment-config",
    "/api/order-enhancement",
    "/api/stores-public",
    "/api/merchant-v1",
    "/api/merchant-dashboard",
    "/api/guardian-system",
    "/api/family-management",
    "/api/points-admin",
    "/api/points-exchange",
    "/api/content",
    "/api/legal/privacy-policy",
    "/api/legal/service-agreement",
    "/api/coupons-admin",
    "/api/admin",
    "/api/admin-merchant",
    "/api/admin-news",
    "/api/admin-messages",
    "/api/admin-search",
    "/api/admin-health-plan",
    "/api/product-admin",
    "/api/wechat-bindding",
    "/api/appointment-form-admin",
    "/api/audit",
    "/api/third-party-openapi",
    "/api/admin-sdk-health",
    "/api/seed-import",
    "/api/admin-family-guardian",
]

all_urls = [(f"{BASE}{p}", "PAGE") for p in frontend_pages] + [(f"{BASE}{p}", "API") for p in backend_apis]

print(f"检查 {len(all_urls)} 个 URL...")
results = []
with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(check_url, u[0]): u for u in all_urls}
    for i, f in enumerate(as_completed(futures)):
        u = futures[f]
        r = f.result()
        r["type"] = u[1]
        results.append(r)
        status = r.get("status", "ERR")
        ok = "✅" if r["ok"] else "❌"
        print(f"[{i+1}/{len(all_urls)}] {ok} {status} {r['url']}")

# Sort by OK status then URL
results.sort(key=lambda x: (not x["ok"], x["url"]))

ok_count = sum(1 for r in results if r["ok"])
fail_count = len(results) - ok_count

print(f"\n=== 结果统计 ===")
print(f"总计: {len(results)}")
print(f"✅ 可达: {ok_count}")
print(f"❌ 不可达: {fail_count}")

print(f"\n=== 不可达 URL ===")
for r in results:
    if not r["ok"]:
        print(f"  {r['type']} {r['status']} {r['url']}")

# Save to JSON
with open("C:\\auto_output\\bnbbaijkgj\\check_results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("\n结果已保存到 check_results.json")
