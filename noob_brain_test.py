"""
Noob Test 全量链接检查脚本
阶段 4.1 + 4.2：全量收集 + HTTPS 可达性检查
"""

import subprocess
import json
import re
import sys
import ssl
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
MAX_WORKERS = 15
CONNECT_TIMEOUT = 5
MAX_TIME = 12
OUTPUT_FILE = "noob_brain_test_results.json"

# ==================== 全量 URL 清单 ====================

# ---- H5 前端页面（基于 h5-web/src/app/ 目录结构） ----
H5_PAGES = [
    "/",
    "/login",
    "/brain-game",
    "/account-security",
    "/ai-home",
    "/ai-home/medication-plans",
    "/ai-home/medication-plans/new",
    "/ai-home/medication-reminder",
    "/ai-settings",
    "/chat-history",
    "/feedback",
    "/address",
    "/alert-redirect",
    "/appointment",
    "/articles",
    "/cards",
    "/cards/wallet",
    "/care-ai-home",
    "/care-ai-home/sos",
    "/care-ai-home/today-health",
    "/care-ai-home/info-card",
    "/care-home",
    "/care-safety-rope",
    "/checkout",
    "/checkup",
    "/checkup/compare",
    "/checkup/compare/select",
    "/checkup/trend",
    "/city-select",
    "/coupon-center",
    "/customer-service",
    "/design-system-v2-preview",
    "/devices",
    "/devices/member",
    "/digital-human-call",
    "/drug",
    "/experts",
    "/family",
    "/family-alert",
    "/family-auth",
    "/family-bindlist",
    "/family-guardian-list",
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
    "/home-safety",
    "/invite",
    "/landing",
    "/legal/privacy-policy",
    "/legal/service-agreement",
    "/medical-records",
    "/medical-records/all",
    "/medical-records/trash",
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
    "/merchant/m/profile",
    "/merchant/m/profile/change-password",
    "/merchant/m/profile/force-change-password",
    "/merchant/m/reports",
    "/merchant/m/select-store",
    "/merchant/m/settlement",
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
    "/merchant/staff",
    "/merchant/store-settings",
    "/merchant/verifications",
    "/merchant/wechat-bindding",
    "/messages",
    "/my-addresses",
    "/my-coupons",
    "/my-favorites",
    "/news",
    "/pay/success",
    "/points",
    "/points/detail",
    "/points/exchange-records",
    "/points/mall",
    "/points/product-detail",
    "/points/records",
    "/profile/edit",
    "/products",
    "/refund-list",
    "/report-history",
    "/sandbox-pay",
    "/scan",
    "/search",
    "/search/result",
    "/services",
    "/settings",
    "/symptom",
    "/tcm",
    "/tcm/archive",
    "/tcm/loading",
    "/unified-orders",
    "/welcome-mode",
]

# ---- Admin 后台页面（基于 admin-web/src/app/(admin)/ 目录结构） ----
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
    "/admin/health-records",
    "/admin/health-records/statistics",
    "/admin/home-banners",
    "/admin/home-safety",
    "/admin/home-settings",
    "/admin/home-settings/ai-home-config",
    "/admin/home-settings/ai-home-config/logs",
    "/admin/knowledge",
    "/admin/map-config",
    "/admin/membership/free-quota",
    "/admin/membership/plans",
    "/admin/merchant/accounts",
    "/admin/merchant/business-config",
    "/admin/merchant/stores",
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
]

# ---- 关键后端 API（全量代表性抽样） ----
CRITICAL_APIS = [
    # 核心健康检查
    ("GET", "/api/health"),
    ("GET", "/api/system/server-time"),
    
    # 脑力游戏 API（本次新增重点）
    ("GET", "/api/brain-game/regions"),
    ("GET", "/api/brain-game/regions/tree"),
    ("GET", "/api/brain-game/rankings"),
    ("GET", "/api/brain-game/challenges/mine"),
    ("GET", "/api/brain-game/user-info"),
    ("GET", "/api/brain-game/wechat-config?url=https://test.com"),
    # POST APIs (will likely return 405 on HEAD, so we test with GET to check routing)
    ("GET", "/api/brain-game/scores"),
    ("GET", "/api/brain-game/challenges"),
    
    # Auth APIs
    ("GET", "/api/auth/me"),
    ("GET", "/api/auth/register-settings"),
    ("GET", "/api/config/login_ui_version"),
    
    # Home config
    ("GET", "/api/home-config"),
    ("GET", "/api/home-menus"),
    ("GET", "/api/home-banners"),
    ("GET", "/api/h5/active-theme"),
    ("GET", "/api/h5/bottom-nav"),
    
    # Family
    ("GET", "/api/family/members"),
    ("GET", "/api/family/management"),
    ("GET", "/api/family/managed-by"),
    ("GET", "/api/family/relation-types"),
    
    # Chat
    ("GET", "/api/chat/sessions"),
    ("GET", "/api/chat/function-buttons"),
    ("GET", "/api/function-buttons"),
    
    # Points & Coupons
    ("GET", "/api/points/balance"),
    ("GET", "/api/points/summary"),
    ("GET", "/api/coupons/mine"),
    
    # Search & Notice
    ("GET", "/api/search/hot"),
    ("GET", "/api/notices/active"),
    
    # Merchant
    ("GET", "/api/merchant/stores"),
    ("GET", "/api/merchant/dashboard"),
    
    # Services & Products
    ("GET", "/api/services/categories"),
    ("GET", "/api/products/categories"),
    ("GET", "/api/products"),
    
    # Messages
    ("GET", "/api/messages/unread-count"),
    
    # Content
    ("GET", "/api/content/articles"),
    ("GET", "/api/content/news"),
    
    # Health
    ("GET", "/api/health/profile"),
    ("GET", "/api/health-dashboard"),
    ("GET", "/api/health-plan/checkin-overview"),
    ("GET", "/api/health-profile-v3"),
    ("GET", "/api/health-archive-v5/overview"),
    
    # Membership
    ("GET", "/api/membership/plans"),
    ("GET", "/api/member/center"),
    
    # TCM & Constitution
    ("GET", "/api/tcm/config"),
    ("GET", "/api/constitution/meta"),
    
    # Report
    ("GET", "/api/report/list"),
    
    # Devices
    ("GET", "/api/devices/catalog"),
    ("GET", "/api/devices/my"),
    
    # Glucose
    ("GET", "/api/glucose-v1/latest"),
    ("GET", "/api/glucose-v1/stats"),
    
    # Safety Rope
    ("GET", "/api/safety-rope/status"),
    
    # Care
    ("GET", "/api/care-v1/home/welcome"),
    ("GET", "/api/care-card/info"),
    
    # Medications
    ("GET", "/api/medication-reminder/plans"),
    ("GET", "/api/medication/today"),
    
    # Questionnaire
    ("GET", "/api/questionnaire/templates"),
    
    # Health self check
    ("GET", "/api/health-self-check/dict"),
    
    # Admin APIs (sampling)
    ("GET", "/api/admin/dashboard"),
    ("GET", "/api/admin/dashboard/stats"),
    ("GET", "/api/admin/users"),
    ("GET", "/api/admin/profile"),
    ("GET", "/api/admin/ai-config"),
    ("GET", "/api/admin/health/users"),
    ("GET", "/api/admin/orders/unified"),
    ("GET", "/api/admin/products"),
    ("GET", "/api/admin/coupons"),
    ("GET", "/api/admin/messages"),
    
    # Docs
    ("GET", "/api/docs"),
    ("GET", "/api/openapi.json"),
]

# ---- 之前确认失败的 URL（重新检查） ----
PREVIOUSLY_FAILED = [
    "/",
    "/care-home",
    "/legal/privacy-policy",
    "/merchant/m/orders/1",
    "/report-history/1",
    "/report-history",
    "/review/1",
    "/admin/email-notify",
    "/admin/guardian-relations",
    "/admin/ocr-config",
    "/admin/orders",
    "/admin/product-system/appointment-forms",
    "/admin/settings",
    "/admin/sms",
    "/api/family/guardians/1",
]

# ---- 动态页面（带参数，检查父路径可达性即可） ----
DYNAMIC_PARENT_PATHS = [
    "/article/1",
    "/cards/1",
    "/cards/redeem-code/1",
    "/cards/renew/1",
    "/cards/usage-logs/1",
    "/care-ai-home/card-view/abc",
    "/care-ai-home/share-location/abc",
    "/chat/abc",
    "/checkup/chat/abc",
    "/checkup/detail/1",
    "/checkup/result/1",
    "/drug/chat/abc",
    "/expert/1",
    "/family-guardian-list/1",
    "/health-plan/custom/1",
    "/health-plan/custom/my-plan/1",
    "/health-plan/custom/plan/1",
    "/health-self-check/result/1",
    "/medical-records/1",
    "/news/1",
    "/order/1",
    "/product/1",
    "/refund/1",
    "/report-history/comparison/1",
    "/report-history/shared/abc",
    "/shared/chat/abc",
    "/shared/drug/abc",
    "/shared/report/abc",
    "/tcm/diagnosis/1",
    "/tcm/result/1",
    "/unified-order/1",
    "/merchant/settlement/1",
    "/merchant/m/settlement/1",
    "/admin/chat-records/1",
    "/admin/health-plan/recommended/1/tasks",
    "/admin/knowledge/1",
    "/admin/merchant/stores/1/business-config",
]

# ==================== 工具函数 ====================

def curl_check(url, follow_redirects=True, timeout=MAX_TIME):
    """使用 curl 检查 URL 可达性，返回 (status_code, redirect_count, detail)"""
    cmd = ["curl", "-Is", "--connect-timeout", str(CONNECT_TIMEOUT), "--max-time", str(timeout)]
    if follow_redirects:
        cmd.extend(["-L", "--max-redirs", "10"])
    cmd.append(url)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        output = result.stdout + result.stderr
        
        codes = re.findall(r'HTTP/\S+\s+(\d{3})', output)
        
        if not codes:
            if result.returncode != 0:
                return (0, 0, "CONNECTION_FAILED", output[:300])
            return (0, 0, "NO_HTTP_RESPONSE", output[:300])
        
        final_code = int(codes[-1])
        redirect_count = len([c for c in codes if c.startswith('30')])
        
        if redirect_count >= 10:
            return (final_code, redirect_count, "REDIRECT_LOOP", f"redirects={redirect_count}")
        
        if final_code < 400 or final_code == 405:
            return (final_code, redirect_count, "OK", f"codes={codes}")
        else:
            return (final_code, redirect_count, "ERROR_HTTP", f"codes={codes}")
    except subprocess.TimeoutExpired:
        return (0, 0, "TIMEOUT", "command timed out")
    except Exception as e:
        return (0, 0, "ERROR", str(e)[:300])

def check_ssl_cert(domain, port=443):
    """检查 SSL 证书"""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                not_after = cert.get('notAfter', '')
                subject = dict(x[0] for x in cert.get('subject', []))
                san = cert.get('subjectAltName', [])
                return {
                    "valid": True,
                    "subject": subject.get('commonName', ''),
                    "not_after": not_after,
                    "san_count": len(san),
                }
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}

def check_one(entry):
    """检查单个 URL"""
    i, total, label, url = entry
    status_code, redirects, status, detail = curl_check(url)
    result = {
        "url": url,
        "label": label,
        "http_status": status_code,
        "redirect_count": redirects,
        "status": status,
        "detail": detail,
    }
    
    # 简短输出
    icon = "✅" if status == "OK" else "❌"
    print(f"[{i:4d}/{total}] {icon} {status_code:3d} | {label:20s} | {url}")
    
    return result

def main():
    print("=" * 80)
    print("  Noob Test — 全量链接可达性检查")
    print(f"  目标域名: {DOMAIN}")
    print(f"  开始时间: {datetime.now().isoformat()}")
    print("=" * 80)
    
    # ---- SSL 证书检查 ----
    print("\n[SSL 证书检查]")
    ssl_result = check_ssl_cert(DOMAIN)
    print(f"  SSL: {ssl_result}")
    
    # ---- 检查内部容器连通性（通过 SSH） ----
    print("\n[后端 API 直连检查]")
    direct_check = curl_check(f"https://{DOMAIN}/api/health")
    print(f"  /api/health: {direct_check}")
    
    # ---- 构建 URL 列表 ----
    all_urls_ordered = []
    
    # 1. 重点：brain-game 页面和 API
    bg_urls = [
        ("H5_BRAIN_GAME", "/brain-game"),
    ]
    for label, path in bg_urls:
        all_urls_ordered.append((label, f"https://{DOMAIN}{path}"))
    
    # 2. 首页和登录
    for path in ["/", "/login"]:
        all_urls_ordered.append(("H5_CORE", f"https://{DOMAIN}{path}"))
    
    # 3. 后端 brain-game API
    for method, path in CRITICAL_APIS:
        if "brain-game" in path:
            all_urls_ordered.append((f"API_{method}", f"https://{DOMAIN}{path}"))
    
    # 4. 之前失败的 URL
    for path in PREVIOUSLY_FAILED:
        if path not in [u[1].replace(f"https://{DOMAIN}", "") for u in all_urls_ordered]:
            all_urls_ordered.append(("RETRY_FAILED", f"https://{DOMAIN}{path}"))
    
    # 5. 其余 H5 页面
    for path in H5_PAGES:
        url = f"https://{DOMAIN}{path}"
        if url not in [u[1] for u in all_urls_ordered]:
            all_urls_ordered.append(("H5_PAGE", url))
    
    # 6. Admin 页面
    for path in ADMIN_PAGES:
        url = f"https://{DOMAIN}{path}"
        if url not in [u[1] for u in all_urls_ordered]:
            all_urls_ordered.append(("ADMIN_PAGE", url))
    
    # 7. 所有关键 API
    for method, path in CRITICAL_APIS:
        url = f"https://{DOMAIN}{path}"
        if url not in [u[1] for u in all_urls_ordered]:
            all_urls_ordered.append((f"API_{method}", url))
    
    # 8. 动态页面
    for path in DYNAMIC_PARENT_PATHS:
        url = f"https://{DOMAIN}{path}"
        if url not in [u[1] for u in all_urls_ordered]:
            all_urls_ordered.append(("H5_DYNAMIC", url))
    
    total = len(all_urls_ordered)
    print(f"\n全量 URL 总数: {total}")
    print(f"并发线程数: {MAX_WORKERS}")
    print("=" * 80)
    
    # ---- 开始检查 ----
    results = []
    entries = [(i+1, total, label, url) for i, (label, url) in enumerate(all_urls_ordered)]
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_one, entry): entry for entry in entries}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    # ---- 分类统计 ----
    reachable = [r for r in results if r["status"] == "OK" and r["http_status"] < 400]
    api_405 = [r for r in results if r["status"] == "OK" and r["http_status"] == 405]
    unreachable = [r for r in results if r["status"] == "ERROR_HTTP" and r["http_status"] >= 400 and r["http_status"] != 405]
    redirect_loops = [r for r in results if r["status"] == "REDIRECT_LOOP"]
    errors = [r for r in results if r["status"] in ("CONNECTION_FAILED", "TIMEOUT", "ERROR", "NO_HTTP_RESPONSE")]
    
    print("\n" + "=" * 80)
    print("  链接检查统计")
    print("=" * 80)
    print(f"  总 URL 数：{total}")
    print(f"  ✅ 可达（2xx/3xx）：{len(reachable)}")
    print(f"  ⚠️  API 405（需认证/POST 转为 GET）：{len(api_405)}")
    print(f"  ❌ 不可达（4xx/5xx 非 405）：{len(unreachable)}")
    print(f"  🔄 重定向循环：{len(redirect_loops)}")
    print(f"  💥 连接失败/超时：{len(errors)}")
    
    # ---- 错误详情 ----
    if unreachable:
        print("\n--- ❌ 不可达 URL（HTTP 4xx/5xx） ---")
        for e in unreachable:
            print(f"  HTTP {e['http_status']}: {e['url']} ({e['detail']})")
    
    if redirect_loops:
        print("\n--- 🔄 重定向循环 ---")
        for e in redirect_loops:
            print(f"  {e['url']} ({e['detail']})")
    
    if errors:
        print("\n--- 💥 连接失败/超时 ---")
        for e in errors:
            print(f"  {e['status']}: {e['url']} ({e['detail'][:100]})")
    
    # ---- 写入 JSON ----
    output = {
        "timestamp": datetime.now().isoformat(),
        "domain": DOMAIN,
        "ssl": ssl_result,
        "total_urls": total,
        "reachable_count": len(reachable),
        "api_405_count": len(api_405),
        "unreachable_count": len(unreachable),
        "redirect_loop_count": len(redirect_loops),
        "error_count": len(errors),
        "reachable": reachable,
        "api_405": api_405,
        "unreachable": unreachable,
        "redirect_loops": redirect_loops,
        "errors": errors,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n结果已写入 {OUTPUT_FILE}")
    
    return output

if __name__ == "__main__":
    main()
