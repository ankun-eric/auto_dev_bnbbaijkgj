"""
批量 URL 可达性检查脚本（阶段 4.2）- 并发版
检查所有前端页面和关键后端 API 的可达性
"""
import subprocess
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
SERVER_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
MAX_WORKERS = 12  # parallel checks
CONNECT_TIMEOUT = 3
MAX_TIME = 10

# ====== H5-WEB Frontend Pages (from app/ directory) ======
H5_PAGES = [
    # Root
    "/",
    # AI Chat (route group (ai-chat) doesn't affect path)
    "/account-security",
    "/ai-home",
    "/ai-home/medication-plans",
    "/ai-home/medication-plans/new",
    "/ai-home/medication-plans/1",
    "/ai-home/medication-reminder",
    "/ai-settings",
    "/chat-history",
    "/feedback",
    # Direct pages
    "/address",
    "/alert-redirect",
    "/appointment",
    "/article/1",
    "/articles",
    "/cards",
    "/cards/1",
    "/cards/redeem-code/1",
    "/cards/renew/1",
    "/cards/usage-logs/1",
    "/cards/wallet",
    "/care-ai-home",
    "/care-ai-home/card-view/abc",
    "/care-ai-home/info-card",
    "/care-ai-home/share-location/abc",
    "/care-ai-home/sos",
    "/care-ai-home/today-health",
    "/care-home",
    "/care-safety-rope",
    "/chat/abc",
    "/checkout",
    "/checkup",
    "/checkup/chat/abc",
    "/checkup/compare",
    "/checkup/compare/select",
    "/checkup/detail/1",
    "/checkup/result/1",
    "/checkup/trend",
    "/city-select",
    "/coupon-center",
    "/customer-service",
    "/design-system-v2-preview",
    "/devices",
    "/devices/member",
    "/digital-human-call",
    "/drug",
    "/drug/chat/abc",
    "/expert/1",
    "/experts",
    "/family",
    "/family-alert",
    "/family-auth",
    "/family-bindlist",
    "/family-guardian-list",
    "/family-guardian-list/1",
    "/family-invite",
    "/glucose",
    "/health-alerts",
    "/health-dashboard",
    "/health-guide",
    "/health-metric/bp",
    "/health-metric/bp/history",
    "/health-plan",
    "/health-plan/checkin",
    "/health-plan/checkin/add",
    "/health-plan/custom",
    "/health-plan/custom/create",
    "/health-plan/custom/1",
    "/health-plan/custom/my-plan/1",
    "/health-plan/custom/plan/1",
    "/health-plan/edit",
    "/health-plan/result",
    "/health-plan/statistics",
    "/health-profile",
    "/health-profile/archive-list",
    "/health-profile/i-guard",
    "/health-profile/my-guardians",
    "/health-profile/my-guardians/invite",
    "/health-profile/v13",
    "/health-reminders",
    "/health-self-check/result/1",
    "/home-safety",
    "/invite",
    "/landing",
    "/legal/privacy-policy",
    "/legal/service-agreement",
    "/login",
    "/medical-records",
    "/medical-records/all",
    "/medical-records/trash",
    "/medical-records/1",
    "/member-card",
    "/member-center",
    "/merchant",
    "/merchant/dashboard",
    "/merchant/downloads",
    "/merchant/finance",
    "/merchant/invoice",
    "/merchant/login",
    "/merchant/m",
    "/merchant/m/dashboard",
    "/merchant/m/downloads",
    "/merchant/m/finance",
    "/merchant/m/invoice",
    "/merchant/m/login",
    "/merchant/m/me",
    "/merchant/m/messages",
    "/merchant/m/orders",
    "/merchant/m/orders/1",
    "/merchant/m/profile",
    "/merchant/m/profile/change-password",
    "/merchant/m/profile/force-change-password",
    "/merchant/m/reports",
    "/merchant/m/select-store",
    "/merchant/m/settlement",
    "/merchant/m/settlement/1",
    "/merchant/m/staff",
    "/merchant/m/store-settings",
    "/merchant/m/verify",
    "/merchant/m/wechat-bindding",
    "/merchant/messages",
    "/merchant/order-dashboard",
    "/merchant/orders",
    "/merchant/profile",
    "/merchant/profile/change-password",
    "/merchant/reports",
    "/merchant/select-store",
    "/merchant/settlement",
    "/merchant/settlement/1",
    "/merchant/staff",
    "/merchant/store-settings",
    "/merchant/verifications",
    "/merchant/wechat-bindding",
    "/messages",
    "/my-addresses",
    "/my-coupons",
    "/my-favorites",
    "/news",
    "/news/1",
    "/order/1",
    "/pay/success",
    "/points",
    "/points/detail",
    "/points/exchange-records",
    "/points/mall",
    "/points/product-detail",
    "/points/records",
    "/product/1",
    "/products",
    "/profile/edit",
    "/refund/1",
    "/refund-list",
    "/report-history",
    "/report-history/1",
    "/report-history/comparison/1",
    "/report-history/shared/abc",
    "/review/1",
    "/sandbox-pay",
    "/scan",
    "/search",
    "/search/result",
    "/services",
    "/settings",
    "/shared/chat/abc",
    "/shared/drug/abc",
    "/shared/report/abc",
    "/symptom",
    "/tcm",
    "/tcm/archive",
    "/tcm/diagnosis/1",
    "/tcm/loading",
    "/tcm/result/1",
    "/unified-order/1",
    "/unified-orders",
    "/welcome-mode",
]

# ====== ADMIN-WEB Frontend Pages ======
ADMIN_PAGES = [
    "/admin",
    "/admin/abnormal-thresholds",
    "/admin/admin-settlements",
    "/admin/ai-call-config",
    "/admin/ai-center/disclaimers",
    "/admin/ai-center/prompts",
    "/admin/ai-center/sensitive-words",
    "/admin/ai-config",
    "/admin/ai-config/chat-timeout",
    "/admin/ai-config/video-consult",
    "/admin/alert-logs",
    "/admin/alert-templates",
    "/admin/audit/center",
    "/admin/audit/phones",
    "/admin/bottom-nav",
    "/admin/chat-records",
    "/admin/chat-records/1",
    "/admin/checkup-details",
    "/admin/city-management",
    "/admin/constitution-content",
    "/admin/content/articles",
    "/admin/content/categories",
    "/admin/content/news",
    "/admin/cos-config",
    "/admin/customer-service",
    "/admin/dashboard",
    "/admin/digital-humans",
    "/admin/disease-presets",
    "/admin/drug-details",
    "/admin/email-notify",
    "/admin/emergency-sources",
    "/admin/experts",
    "/admin/fallback-config",
    "/admin/family-management",
    "/admin/function-buttons",
    "/admin/guardian-relations",
    "/admin/health-plan/categories",
    "/admin/health-plan/recommended",
    "/admin/health-plan/recommended/1/tasks",
    "/admin/health-records",
    "/admin/health-records/statistics",
    "/admin/home-banners",
    "/admin/home-safety",
    "/admin/home-settings",
    "/admin/home-settings/ai-home-config",
    "/admin/home-settings/ai-home-config/logs",
    "/admin/knowledge",
    "/admin/knowledge/1",
    "/admin/knowledge/stats",
    "/admin/map-config",
    "/admin/membership/free-quota",
    "/admin/membership/plans",
    "/admin/merchant/accounts",
    "/admin/merchant/business-config",
    "/admin/merchant/stores",
    "/admin/merchant/stores/1/business-config",
    "/admin/merchant-categories",
    "/admin/notices",
    "/admin/ocr-config",
    "/admin/ocr-global-config",
    "/admin/orders",
    "/admin/payment-config",
    "/admin/points/levels",
    "/admin/points/mall",
    "/admin/points/rules",
    "/admin/product-system/appointment-forms",
    "/admin/product-system/cards",
    "/admin/product-system/cards/dashboard",
    "/admin/product-system/categories",
    "/admin/product-system/coupons",
    "/admin/product-system/new-user-coupons",
    "/admin/product-system/orders",
    "/admin/product-system/orders/dashboard",
    "/admin/product-system/partners",
    "/admin/product-system/products",
    "/admin/product-system/redemptions",
    "/admin/product-system/statistics",
    "/admin/product-system/store-bindding",
    "/admin/product-system/tags",
    "/admin/product-system/visits",
    "/admin/profile",
    "/admin/profile/change-password",
    "/admin/prompt-templates",
    "/admin/questionnaire-templates",
    "/admin/referral",
    "/admin/relation-types",
    "/admin/search/asr-config",
    "/admin/search/block-words",
    "/admin/search/recommend",
    "/admin/search/statistics",
    "/admin/search-config",
    "/admin/settings",
    "/admin/share-config",
    "/admin/sms",
    "/admin/system/sdk-health",
    "/admin/system/seed-import",
    "/admin/system-messages",
    "/admin/system-messages/send",
    "/admin/tcm-config",
    "/admin/theme-config",
    "/admin/tts-config",
    "/admin/users",
    "/admin/voice-service",
    "/admin/wechat-push",
    "/login",  # admin login
]

# ====== Critical Backend APIs (Family related + key endpoints) ======
CRITICAL_APIS = [
    # Family/Invitation APIs (focus of this test)
    ("GET", "/api/family/invitation/ABC123"),
    ("GET", "/api/family/members"),
    ("POST", "/api/family/invitation/ABC123/accept"),
    ("GET", "/api/family/management"),
    ("GET", "/api/family/managed-by"),
    ("GET", "/api/family/members/1"),
    ("GET", "/api/family/guardians/1"),
    ("POST", "/api/family/invitation"),
    ("POST", "/api/family/invitation/ABC123/reject"),
    # Core auth APIs
    ("GET", "/api/auth/me"),
    ("GET", "/api/auth/register-settings"),
    ("GET", "/api/health"),
    ("GET", "/api/system/server-time"),
    # Key feature APIs
    ("GET", "/api/chat/sessions"),
    ("GET", "/api/home-config"),
    ("GET", "/api/home-menus"),
    ("GET", "/api/home-banners"),
    ("GET", "/api/messages/unread-count"),
    ("GET", "/api/points/balance"),
    ("GET", "/api/points/summary"),
    ("GET", "/api/coupons/mine"),
    ("GET", "/api/search/hot"),
    ("GET", "/api/notices/active"),
    ("GET", "/api/merchant/stores"),
    ("GET", "/api/services/categories"),
]

def curl_check(url, follow_redirects=True):
    """使用 curl 检查 URL 可达性"""
    cmd = ["curl", "-Is", "--connect-timeout", str(CONNECT_TIMEOUT), "--max-time", str(MAX_TIME)]
    if follow_redirects:
        cmd.extend(["-L", "--max-redirs", "10"])
    cmd.append(url)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=MAX_TIME+5)
        output = result.stdout + result.stderr
        
        codes = re.findall(r'HTTP/\S+\s+(\d{3})', output)
        
        if not codes:
            if result.returncode != 0:
                return ("TIMEOUT/CONNECTION_FAILED", output[:300])
            return ("NO_HTTP_RESPONSE", output[:300])
        
        final_code = int(codes[-1])
        
        redirect_count = len([c for c in codes if c.startswith('30')])
        if redirect_count >= 10:
            return ("REDIRECT_LOOP", f"redirects={redirect_count}, codes={codes}")
        
        if final_code < 400 or final_code == 405:
            return (f"REACHABLE({final_code})", f"codes={codes}")
        else:
            return (f"UNREACHABLE({final_code})", f"codes={codes}")
    except subprocess.TimeoutExpired:
        return ("TIMEOUT", "command timed out")
    except Exception as e:
        return ("ERROR", str(e)[:300])

def check_one(entry):
    """Check one URL, return result dict"""
    i, total, label, url = entry
    status, detail = curl_check(url)
    print(f"[{i}/{total}] {status:30s} {label:15s} {url}")
    return {
        "url": url,
        "label": label,
        "status": status,
        "detail": detail
    }

def main():
    results = {"reachable": [], "unreachable": [], "redirect_loops": [], "errors": []}
    
    all_urls = []
    
    # Add H5 pages
    for path in H5_PAGES:
        url = f"https://{DOMAIN}{path}"
        all_urls.append(("H5_PAGE", url))
    
    # Add Admin pages  
    for path in ADMIN_PAGES:
        url = f"https://{DOMAIN}{path}"
        all_urls.append(("ADMIN_PAGE", url))
    
    # Add critical APIs
    for method, path in CRITICAL_APIS:
        url = f"https://{DOMAIN}{path}"
        all_urls.append((f"API_{method}", url))
    
    total = len(all_urls)
    print(f"Total URLs to check: {total}")
    print(f"Domain: {DOMAIN}")
    print(f"Concurrency: {MAX_WORKERS} workers")
    print("="*80)
    
    entries = [(i+1, total, label, url) for i, (label, url) in enumerate(all_urls)]
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_one, entry): entry for entry in entries}
        for future in as_completed(futures):
            result = future.result()
            
            if "REACHABLE" in result["status"]:
                results["reachable"].append(result)
            elif "REDIRECT_LOOP" in result["status"]:
                results["redirect_loops"].append(result)
            elif "UNREACHABLE" in result["status"]:
                results["unreachable"].append(result)
            else:
                results["errors"].append(result)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total URLs checked: {total}")
    print(f"Reachable: {len(results['reachable'])}")
    print(f"Unreachable (4xx/5xx): {len(results['unreachable'])}")
    print(f"Redirect loops: {len(results['redirect_loops'])}")
    print(f"Errors (timeout/connection): {len(results['errors'])}")
    
    # Detailed unreachable list
    if results["unreachable"]:
        print("\n--- UNREACHABLE URLs ---")
        for e in results["unreachable"]:
            print(f"  {e['status']}: {e['url']}")
    
    if results["redirect_loops"]:
        print("\n--- REDIRECT LOOP URLs ---")
        for e in results["redirect_loops"]:
            print(f"  {e['url']}")
    
    if results["errors"]:
        print("\n--- ERROR URLs ---")
        for e in results["errors"]:
            print(f"  {e['status']}: {e['url']}")
    
    # Write results to JSON
    with open("check_results_final.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nResults written to check_results_final.json")
    
    return results

if __name__ == "__main__":
    main()
