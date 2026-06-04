import subprocess
import json
import sys
import re
import os

DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

# Core API GET endpoints (extracted from backend route analysis)
API_URLS = [
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/auth/register-settings",
    "/api/auth/me",
    "/api/users/me",
    "/api/user/font-setting",
    "/api/user/health-profile",
    "/api/user/mode-preference",
    "/api/family/members",
    "/api/family/relation-types",
    "/api/family/disease-presets",
    "/api/points/balance",
    "/api/points/records",
    "/api/points/summary",
    "/api/points/tasks",
    "/api/points/mall/products",
    "/api/points/mall",
    "/api/points/checkin/today-progress",
    "/api/points/exchange-records",
    "/api/orders/unified",
    "/api/orders/unified/counts",
    "/api/products/categories",
    "/api/products",
    "/api/products/hot-recommendations",
    "/api/services/categories",
    "/api/services/items",
    "/api/services/list",
    "/api/search",
    "/api/search/suggest",
    "/api/search/hot",
    "/api/search/history",
    "/api/search/drug-keywords",
    "/api/experts",
    "/api/cities/list",
    "/api/cities/hot",
    "/api/cities/locate",
    "/api/content/articles",
    "/api/content/article-categories",
    "/api/content/news",
    "/api/content/news/latest",
    "/api/content/favorites",
    "/api/favorites",
    "/api/favorites/status",
    "/api/notifications",
    "/api/v1/notifications/unread-count",
    "/api/messages",
    "/api/messages/unread-count",
    "/api/notices/active",
    "/api/drugs/search",
    "/api/health/profile",
    "/api/health/guide-status",
    "/api/health/allergies",
    "/api/health/medical-history",
    "/api/health/medications",
    "/api/health/visits",
    "/api/health/checkup-reports",
    "/api/report/list",
    "/api/report/alerts",
    "/api/report-history/list",
    "/api/tcm/diagnosis",
    "/api/tcm/questions",
    "/api/tcm/config",
    "/api/constitution/archive",
    "/api/health-plan/template-categories",
    "/api/health-plan/checkin-overview",
    "/api/health-plan/checkin-calendar",
    "/api/health-plan/checkin-stats-summary",
    "/api/health-plan/medications",
    "/api/health-plan/medications/list",
    "/api/health-plan/medications/summary",
    "/api/health-plan/checkin-items",
    "/api/cards",
    "/api/cards/me/wallet",
    "/api/coupons/available",
    "/api/coupons/summary",
    "/api/coupons/mine",
    "/api/membership/plans",
    "/api/member/center",
    "/api/member/plans",
    "/api/member/quota-usage",
    "/api/medication-reminder/plans",
    "/api/medication-reminder/today",
    "/api/medication-reminder/badge",
    "/api/medication-reminder/appointments",
    "/api/health-archive-v5/overview",
    "/api/health-profile",
    "/api/health-profile/self",
    "/api/health-metric-v1/meta",
    "/api/prd469/family-member/relation-options",
    "/api/prd469/device/list",
    "/api/prd469/health-event/timeline",
    "/api/prd469/care-partners",
    "/api/devices/catalog",
    "/api/devices/my",
    "/api/glucose-v1/records",
    "/api/glucose-v1/stats",
    "/api/glucose-v1/alerts",
    "/api/glucose-v1/ai-advice",
    "/api/glucose-v1/report",
    "/api/glucose-v1/reminder",
    "/api/glucose-v1/latest",
    "/api/ai-home/refresh-config",
    "/api/ai-home-config",
    "/api/home-config",
    "/api/home-menus",
    "/api/home-banners",
    "/api/function-buttons",
    "/api/health-self-check/placeholder-catalog",
    "/api/questionnaire/placeholder-catalog",
    "/api/questionnaire/templates",
    "/api/consultant/1/profile_card",
    "/api/care/daily-summary",
    "/api/care/alerts/active",
    "/api/care-v1/user-preferences",
    "/api/care-v1/home/welcome",
    "/api/care-v1/home/proactive-cards",
    "/api/care-v1/sos/keywords",
    "/api/care-v1/sos/events",
    "/api/care-card/contacts",
    "/api/care-card/info",
    "/api/care-card/qr-token",
    "/api/guardian/v13/family/list",
    "/api/guardian/v13/family/invite-history",
    "/api/guardian/v13/family/proxy-pay/detail",
    "/api/guardian/v12/i-guard",
    "/api/guardian/v12/ai-call-quota",
    "/api/guardian/v12/emergency-quota",
    "/api/guardian/v12/managed-quota-summary",
    "/api/guardian/v12/invitations/records",
    "/api/reverse-guardian/my-guardians",
    "/api/reverse-guardian/guardian-count",
    "/api/safety-rope/status",
    "/api/safety-rope/checkins",
    "/api/safety-rope/contacts",
    "/api/safety-rope/alerts",
    "/api/medication-plans/today",
    "/api/medication-plans/hero-count",
    "/api/medication-plans/summary",
    "/api/medication-stats/monthly-compliance",
    "/api/medication-library/suggest",
    "/api/medication-library/search",
    "/api/medication-library/stats",
    "/api/chat-sessions",
    "/api/chat-sessions/active",
    "/api/chat-sessions/active-check",
    "/api/health-alerts",
    "/api/medical-records",
    "/api/medical-records/trash",
    "/api/family-archive-v2/members",
    "/api/family-archive-v2/hero-counts",
    "/api/health-archive/guardian/summary",
    "/api/health-archive/family-members/guarded-flags",
    "/api/health-archive/ai-call/settings",
    "/api/family/guardians/1",
    "/api/me/alert-logs",
    "/api/system/server-time",
    "/api/common/time-slots",
    "/api/h5/checkout/init",
    "/api/h5/slots",
    "/api/h5/checkout/info",
    "/api/pay/available-methods",
    "/api/addresses",
    "/api/v2/regions",
    "/api/v2/user/addresses",
    "/api/v2/app/version-check",
    "/api/cos/upload-limits",
    "/api/app-settings/page-style",
    "/api/app-settings/chat-idle-timeout",
    "/api/h5/active-theme",
    "/api/config/login_ui_version",
    "/api/users/share-link",
    "/api/landing",
    "/api/users/invite-stats",
    "/api/scan",
    "/api/member/qrcode",
    "/api/merchant-categories",
    "/api/auth/merchant-status",
    "/api/family/member/state/list",
    "/api/family/member/quota",
    "/api/settings/tts-config",
    "/api/feedback",
    "/api/family/management",
    "/api/family/managed-by",
    "/api/health-dashboard/1",
    "/api/health-reminders",
    "/api/health-reminders/recommendations",
    "/api/health-profile-v3/1/today-metrics",
    "/api/health-metric-v1/1/bp/history",
    "/api/bp-v1/ai-explain-single",
    "/api/prd469/summary-stats/1",
    "/api/v1/consultant/1/profile_card",
]

# H5 page routes (from h5-web/src/app page.tsx analysis)
H5_URLS = [
    "/",
    "/login",
    "/ai-home",
    "/family",
    "/family-guardian-list",
    "/family-invite",
    "/family-auth",
    "/family-bindlist",
    "/health-profile",
    "/health-profile/my-guardians",
    "/health-profile/my-guardians/invite",
    "/health-profile/i-guard",
    "/health-profile/v13",
    "/health-profile/archive-list",
    "/health-dashboard",
    "/health-plan",
    "/health-plan/checkin",
    "/health-plan/result",
    "/health-plan/edit",
    "/health-plan/custom",
    "/health-plan/custom/create",
    "/health-plan/statistics",
    "/health-metric/bp",
    "/health-metric/bp/history",
    "/health-alerts",
    "/health-reminders",
    "/health-guide",
    "/health-self-check",
    "/member-center",
    "/member-card",
    "/messages",
    "/care-ai-home",
    "/care-ai-home/sos",
    "/care-ai-home/today-health",
    "/care-ai-home/info-card",
    "/care-home",
    "/care-safety-rope",
    "/home-safety",
    "/tcm",
    "/tcm/archive",
    "/tcm/loading",
    "/chat",
    "/chat-history",
    "/ai-settings",
    "/account-security",
    "/feedback",
    "/search",
    "/search/result",
    "/products",
    "/services",
    "/appointment",
    "/expert",
    "/experts",
    "/articles",
    "/article",
    "/news",
    "/checkup",
    "/checkup/compare",
    "/checkup/trend",
    "/report-history",
    "/devices",
    "/devices/member",
    "/address",
    "/my-addresses",
    "/settings",
    "/profile/edit",
    "/scan",
    "/invite",
    "/coupon-center",
    "/my-coupons",
    "/points",
    "/points/mall",
    "/points/product-detail",
    "/points/detail",
    "/points/records",
    "/points/exchange-records",
    "/my-favorites",
    "/customer-service",
    "/checkout",
    "/unified-orders",
    "/refund-list",
    "/pay/success",
    "/sandbox-pay",
    "/cards",
    "/cards/wallet",
    "/welcome-mode",
    "/drug",
    "/digital-human-call",
    "/medical-records",
    "/medical-records/all",
    "/medical-records/trash",
    "/city-select",
    "/alert-redirect",
    "/family-alert",
    "/glucose",
    "/symptom",
    "/landing",
    "/design-system-v2-preview",
    "/merchant/login",
    "/merchant/dashboard",
    "/legal/privacy-policy",
    "/legal/service-agreement",
]

# Admin page routes (from admin-web/src/app page.tsx analysis)
ADMIN_URLS = [
    "/admin",
    "/admin/login",
    "/admin/dashboard",
    "/admin/users",
    "/admin/family-management",
    "/admin/guardian-relations",
    "/admin/home-safety",
    "/admin/alert-logs",
    "/admin/abnormal-thresholds",
    "/admin/alert-templates",
    "/admin/emergency-sources",
    "/admin/health-records",
    "/admin/health-records/statistics",
    "/admin/health-plan/categories",
    "/admin/health-plan/recommended",
    "/admin/settings",
    "/admin/home-settings",
    "/admin/home-settings/ai-home-config",
    "/admin/home-settings/ai-home-config/logs",
    "/admin/ai-config",
    "/admin/ai-config/chat-timeout",
    "/admin/ai-config/video-consult",
    "/admin/ai-center/prompts",
    "/admin/ai-center/disclaimers",
    "/admin/ai-center/sensitive-words",
    "/admin/ai-call-config",
    "/admin/prompt-templates",
    "/admin/function-buttons",
    "/admin/questionnaire-templates",
    "/admin/constitution-content",
    "/admin/tcm-config",
    "/admin/bottom-nav",
    "/admin/map-config",
    "/admin/theme-config",
    "/admin/product-system/products",
    "/admin/product-system/orders",
    "/admin/product-system/coupons",
    "/admin/product-system/cards",
    "/admin/product-system/cards/dashboard",
    "/admin/product-system/tags",
    "/admin/product-system/categories",
    "/admin/product-system/statistics",
    "/admin/product-system/visits",
    "/admin/product-system/redemptions",
    "/admin/product-system/appointment-forms",
    "/admin/product-system/partners",
    "/admin/product-system/new-user-coupons",
    "/admin/product-system/orders/dashboard",
    "/admin/product-system/store-bindding",
    "/admin/points/levels",
    "/admin/points/mall",
    "/admin/points/rules",
    "/admin/membership/plans",
    "/admin/membership/free-quota",
    "/admin/merchant/accounts",
    "/admin/merchant/stores",
    "/admin/merchant/business-config",
    "/admin/merchant-categories",
    "/admin/payment-config",
    "/admin/content/articles",
    "/admin/content/categories",
    "/admin/content/news",
    "/admin/knowledge",
    "/admin/knowledge/stats",
    "/admin/search/statistics",
    "/admin/search/recommend",
    "/admin/search/block-words",
    "/admin/search/asr-config",
    "/admin/search-config",
    "/admin/fallback-config",
    "/admin/cos-config",
    "/admin/ocr-config",
    "/admin/ocr-global-config",
    "/admin/system/sdk-health",
    "/admin/system/seed-import",
    "/admin/system-messages",
    "/admin/system-messages/send",
    "/admin/sms",
    "/admin/email-notify",
    "/admin/wechat-push",
    "/admin/notices",
    "/admin/experts",
    "/admin/chat-records",
    "/admin/drug-details",
    "/admin/checkup-details",
    "/admin/digital-humans",
    "/admin/voice-service",
    "/admin/tts-config",
    "/admin/share-config",
    "/admin/disease-presets",
    "/admin/relation-types",
    "/admin/city-management",
    "/admin/home-banners",
    "/admin/customer-service",
    "/admin/audit/center",
    "/admin/audit/phones",
    "/admin/referral",
    "/admin/admin-settlements",
    "/admin/profile",
    "/admin/profile/change-password",
]


def check_url(url, timeout=15):
    """Check if URL is reachable, returns (url, http_code, effective_url, error)"""
    try:
        # Use -k to skip SSL verification, -L to follow redirects, -w for http_code
        # Use -o NUL to discard body, --connect-timeout for timeout
        cmd = [
            "curl", "-k", "-s", "-L",
            "-o", "NUL",
            "-w", "%{http_code} %{url_effective}",
            "--connect-timeout", str(timeout),
            "--max-time", str(timeout + 10),
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
        output = result.stdout.strip()
        
        if result.returncode == 0 or (result.returncode != 0 and output):
            parts = output.split(None, 1)
            http_code = parts[0] if parts else "000"
            effective_url = parts[1] if len(parts) > 1 else url
            return url, http_code, effective_url, None
        else:
            err = result.stderr.strip() if result.stderr else "curl exit code {}".format(result.returncode)
            return url, "000", url, err
    except subprocess.TimeoutExpired:
        return url, "000", url, "timeout"
    except Exception as e:
        return url, "000", url, str(e)


def main():
    # Build all URL lists
    all_urls = {}
    base = f"https://{DOMAIN}"
    
    for path in API_URLS:
        all_urls[f"{base}{path}"] = "API"
    for path in H5_URLS:
        all_urls[f"{base}{path}"] = "H5"
    for path in ADMIN_URLS:
        all_urls[f"{base}{path}"] = "Admin"
    
    print(f"Total URLs to check: {len(all_urls)}")
    print(f"  API: {len(API_URLS)}")
    print(f"  H5: {len(H5_URLS)}") 
    print(f"  Admin: {len(ADMIN_URLS)}")
    print()
    
    results = []
    reachable = 0
    unreachable = 0
    redirects = []
    
    for i, (url, category) in enumerate(all_urls.items()):
        if i % 20 == 0:
            print(f"Progress: {i}/{len(all_urls)}...")
        
        url_checked, http_code, effective_url, error = check_url(url)
        
        is_reachable = http_code in ("200", "301", "302", "304", "307", "308", "401", "403")
        # 301/302 are redirects (followed by -L), 401/403 are auth-protected but reachable
        
        if is_reachable:
            reachable += 1
        else:
            unreachable += 1
        
        # Check for redirect loops or /api/api/ double prefix
        has_redirect = effective_url.rstrip("/") != url.rstrip("/")
        has_double_api = "/api/api/" in effective_url
        
        status = "OK" if is_reachable else f"FAIL({http_code})"
        results.append({
            "url": url,
            "category": category,
            "http_code": http_code,
            "effective_url": effective_url,
            "error": error,
            "status": status,
            "redirect": has_redirect,
            "double_api": has_double_api,
        })
        
        if has_redirect:
            redirects.append((url, effective_url))
        if has_double_api:
            print(f"  WARNING: Double /api/api/ detected: {url} -> {effective_url}")
    
    print(f"\n{'='*80}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"Total: {len(results)}")
    print(f"Reachable: {reachable}")
    print(f"Unreachable: {unreachable}")
    print(f"Success rate: {reachable/len(results)*100:.1f}%")
    print()
    
    # Show unreachable
    if unreachable > 0:
        print(f"{'='*80}")
        print(f"UNREACHABLE URLs ({unreachable}):")
        print(f"{'='*80}")
        for r in results:
            if r["status"] != "OK":
                code = r["http_code"]
                issue = "DEPLOYMENT" if code in ("000", "502", "503", "504") else "DEV"
                print(f"  [{issue}] {r['status']:12s} {r['url']}")
                if r["error"]:
                    print(f"         Error: {r['error']}")
        print()
    
    # Show redirects
    if redirects:
        print(f"\n{'='*80}")
        print(f"REDIRECTS DETECTED ({len(redirects)}):")
        print(f"{'='*80}")
        for src, dst in redirects:
            print(f"  {src}")
            print(f"    -> {dst}")
        print()
    
    # Check for /api/api/ double prefix
    double_api = [r for r in results if r["double_api"]]
    if double_api:
        print(f"\n{'='*80}")
        print(f"/api/api/ DOUBLE PREFIX DETECTED ({len(double_api)}):")
        print(f"{'='*80}")
        for r in double_api:
            print(f"  {r['url']} -> {r['effective_url']}")
        print()
    
    # Write detailed results
    with open("link_check_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Detailed results written to link_check_results.json")
    
    # Write summary
    with open("link_check_summary.txt", "w") as f:
        f.write(f"Link Check Summary\n")
        f.write(f"{'='*80}\n")
        f.write(f"Domain: {DOMAIN}\n")
        f.write(f"Total URLs: {len(results)}\n")
        f.write(f"Reachable: {reachable}\n")
        f.write(f"Unreachable: {unreachable}\n")
        f.write(f"Success rate: {reachable/len(results)*100:.1f}%\n\n")
        
        f.write(f"--- UNREACHABLE ---\n")
        for r in results:
            if r["status"] != "OK":
                code = r["http_code"]
                issue = "DEPLOYMENT" if code in ("000", "502", "503", "504") else "DEV"
                f.write(f"  [{issue}] {r['status']:12s} {r['url']}\n")
                if r["error"]:
                    f.write(f"         Error: {r['error']}\n")
        
        f.write(f"\n--- REDIRECTS ---\n")
        for src, dst in redirects:
            f.write(f"  {src} -> {dst}\n")
        
        f.write(f"\n--- DOUBLE /api/api/ ---\n")
        for r in double_api:
            f.write(f"  {r['url']} -> {r['effective_url']}\n")
    
    return results

if __name__ == "__main__":
    main()
