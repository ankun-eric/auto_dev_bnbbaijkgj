"""
全量链接可达性检查脚本
对前端页面和后端 API 执行批量 HTTPS 检查
"""
import subprocess
import json
import re
import sys
import time
import os
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
BASE_URL = f"https://{PROJECT_DOMAIN}"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "link_check_results.json")
ROUTES_FILE = os.path.join(SCRIPT_DIR, "all_routes_extracted.json")

# 创建不验证 SSL 的上下文（用于测试环境）
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# ============================================================
# 前端页面 URL（来源：子 Agent B 扫描 admin-web + h5-web）
# ============================================================
# Admin 路由通过 /admin/ 前缀访问（gateway 路由规则）
# H5 路由直接通过 / 访问

ADMIN_ROUTES = [
    "/", "/abnormal-thresholds", "/admin-settlements", "/ai-call-config",
    "/ai-config", "/alert-logs", "/alert-templates", "/bottom-nav",
    "/chat-records", "/checkup-details", "/city-management",
    "/constitution-content", "/cos-config", "/customer-service",
    "/dashboard", "/digital-humans", "/disease-presets",
    "/drug-details", "/email-notify", "/emergency-sources",
    "/experts", "/fallback-config", "/family-management",
    "/function-buttons", "/guardian-relations", "/health-records",
    "/home-banners", "/home-safety", "/home-settings", "/knowledge",
    "/login", "/map-config", "/merchant-categories", "/notices",
    "/ocr-config", "/ocr-global-config", "/payment-config",
    "/profile", "/prompt-templates", "/questionnaire-templates",
    "/referral", "/refunds", "/relation-types", "/search-config",
    "/settings", "/share-config", "/sms", "/system-messages",
    "/tcm-config", "/theme-config", "/tts-config", "/users",
    "/voice-service", "/wechat-push",
    "/ai-center/disclaimers", "/ai-center/prompts",
    "/ai-center/sensitive-words",
    "/ai-config/chat-timeout", "/ai-config/video-consult",
    "/audit/center", "/audit/phones",
    "/chat-records/1",
    "/content/articles", "/content/categories", "/content/news",
    "/devices/catalog", "/devices/scene-groups",
    "/health-plan/categories", "/health-plan/recommended",
    "/health-records/statistics",
    "/home-settings/ai-home-config",
    "/knowledge/1", "/knowledge/stats",
    "/membership/free-quota", "/membership/plans",
    "/merchant/accounts", "/merchant/business-config",
    "/merchant/stores",
    "/points/levels", "/points/mall", "/points/rules",
    "/product-system/appointment-forms", "/product-system/cards",
    "/product-system/categories", "/product-system/coupons",
    "/product-system/new-user-coupons", "/product-system/orders",
    "/product-system/partners", "/product-system/products",
    "/product-system/redemptions", "/product-system/statistics",
    "/product-system/store-bindding", "/product-system/tags",
    "/product-system/visits",
    "/profile/change-password",
    "/search/asr-config", "/search/block-words",
    "/search/recommend", "/search/statistics",
    "/system-messages/send",
    "/system/sdk-health", "/system/seed-import",
    "/home-settings/ai-home-config/logs",
    "/product-system/cards/dashboard",
    "/product-system/orders/dashboard",
    "/health-plan/recommended/1/tasks",
    "/merchant/stores/1/business-config",
]

H5_ROUTES = [
    "/", "/account-security", "/address", "/ai-home", "/ai-settings",
    "/alert-redirect", "/appointment", "/articles", "/brain-game",
    "/cards", "/care-ai-home", "/care-safety-rope", "/chat-history",
    "/checkout", "/checkup", "/city-select", "/coupon-center",
    "/customer-service", "/design-system-v2-preview", "/devices",
    "/digital-human-call", "/drug", "/experts", "/family-alert",
    "/family-auth", "/family-bindlist", "/family-guardian-list",
    "/family-invite", "/feedback", "/glucose", "/health-alerts",
    "/health-dashboard", "/health-guide", "/health-plan",
    "/health-profile", "/health-reminders", "/home-safety",
    "/invite", "/landing", "/login", "/medical-records",
    "/member-card", "/member-center", "/merchant", "/messages",
    "/my-addresses", "/my-coupons", "/my-favorites", "/news",
    "/points", "/products", "/refund-list", "/report-history",
    "/sandbox-pay", "/scan", "/search", "/services", "/settings",
    "/symptom", "/tcm", "/unified-orders", "/welcome-mode",
    "/ai-home/medication-plans", "/ai-home/medication-reminder",
    "/article/1", "/cards/1", "/cards/wallet",
    "/care-ai-home/info-card", "/care-ai-home/sos",
    "/care-ai-home/today-health", "/chat/1",
    "/checkup/compare", "/checkup/trend", "/devices/member",
    "/expert/1", "/family-guardian-list/1",
    "/health-metric/1", "/health-plan/checkin",
    "/health-plan/custom", "/health-plan/edit",
    "/health-plan/result", "/health-plan/statistics",
    "/health-profile/archive-list", "/health-profile/i-guard",
    "/health-profile/my-guardians", "/health-profile/v13",
    "/legal/privacy-policy", "/legal/service-agreement",
    "/medical-records/1", "/medical-records/all",
    "/medical-records/trash",
    "/merchant/dashboard", "/merchant/downloads",
    "/merchant/finance", "/merchant/invoice",
    "/merchant/login", "/merchant/m", "/merchant/messages",
    "/merchant/order-dashboard", "/merchant/orders",
    "/merchant/profile", "/merchant/reports",
    "/merchant/select-store", "/merchant/settlement",
    "/merchant/staff", "/merchant/store-settings",
    "/merchant/verifications", "/merchant/wechat-bindding",
    "/news/1", "/order/1", "/pay/success",
    "/points/detail", "/points/exchange-records",
    "/points/mall", "/points/product-detail",
    "/points/records", "/product/1", "/profile/edit",
    "/refund/1", "/report-history/1", "/review/1",
    "/search/result", "/tcm/archive", "/tcm/loading",
    "/unified-order/1",
    "/ai-home/medication-plans/1",
    "/ai-home/medication-plans/new",
    "/cards/redeem-code/1", "/cards/renew/1",
    "/cards/usage-logs/1",
    "/care-ai-home/card-view/test",
    "/care-ai-home/share-location/test",
    "/checkup/chat/1", "/checkup/compare/select",
    "/checkup/detail/1", "/checkup/result/1",
    "/drug/chat/1", "/health-metric/1/history",
    "/health-plan/checkin/add",
    "/health-plan/custom/1", "/health-plan/custom/create",
    "/health-profile/my-guardians/invite",
    "/health-self-check/result/1",
    "/merchant/m/dashboard", "/merchant/m/downloads",
    "/merchant/m/finance", "/merchant/m/invoice",
    "/merchant/m/login", "/merchant/m/me",
    "/merchant/m/messages", "/merchant/m/orders",
    "/merchant/m/profile", "/merchant/m/reports",
    "/merchant/m/select-store", "/merchant/m/settlement",
    "/merchant/m/staff", "/merchant/m/store-settings",
    "/merchant/m/verify", "/merchant/m/wechat-bindding",
    "/merchant/profile/change-password",
    "/merchant/settlement/1",
    "/report-history/comparison/1",
    "/report-history/shared/test",
    "/shared/chat/test", "/shared/drug/test",
    "/shared/report/test",
    "/tcm/diagnosis/1", "/tcm/result/1",
    "/health-plan/custom/my-plan/1",
    "/health-plan/custom/plan/1",
    "/merchant/m/orders/1",
    "/merchant/m/profile/change-password",
    "/merchant/m/profile/force-change-password",
    "/merchant/m/settlement/1",
]

def load_and_dedup_backend_routes():
    """从 all_routes_extracted.json 加载后端路由并按路径去重"""
    if not os.path.exists(ROUTES_FILE):
        print(f"路由文件不存在: {ROUTES_FILE}")
        return []
    with open(ROUTES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    backend_routes = data.get('backend', [])
    # 按路径去重，保留第一个出现的
    seen = set()
    unique = []
    for r in backend_routes:
        path = r['path']
        # 替换动态参数
        clean_path = re.sub(r'\{[^}]+\}', '1', path)
        if clean_path not in seen:
            seen.add(clean_path)
            unique.append({
                'method': r['method'],
                'path': clean_path,
                'original_path': path
            })
    return unique

def check_url(url, timeout=15):
    """检查单个 URL 的可达性，返回 (url, status_code, redirect_count, final_url, error)"""
    result = {
        'url': url,
        'status_code': None,
        'redirect_count': 0,
        'final_url': url,
        'error': None,
        'ssl_ok': True
    }
    try:
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'NoobTest/1.0')
        # 使用自定义 opener 处理重定向
        opener = urllib.request.build_opener(
            urllib.request.HTTPRedirectHandler(),
            urllib.request.HTTPSHandler(context=SSL_CONTEXT)
        )
        resp = opener.open(req, timeout=timeout)
        result['status_code'] = resp.getcode()
        result['final_url'] = resp.geturl()
        # 计算重定向次数（简化：如果最终 URL 不同于请求 URL）
        if resp.geturl() != url:
            result['redirect_count'] = 1  # 简化
        resp.close()
    except urllib.error.HTTPError as e:
        result['status_code'] = e.code
    except urllib.error.URLError as e:
        result['error'] = str(e.reason)
        if 'SSL' in str(e.reason) or 'certificate' in str(e.reason).lower():
            result['ssl_ok'] = False
    except Exception as e:
        result['error'] = str(e)
    return result

def check_url_curl(url, timeout=15):
    """使用 curl 检查 URL 可更准确追踪重定向"""
    try:
        cmd = [
            'curl', '-ILs', '--connect-timeout', '5', '--max-time', str(timeout),
            '--max-redirs', '10', '-o', '/dev/null', '-w',
            '%{http_code}|%{num_redirects}|%{url_effective}|%{ssl_verify_result}',
            url
        ]
        # Windows 用不同写法
        if sys.platform == 'win32':
            cmd = [
                'curl', '-ILs', '--connect-timeout', '5', '--max-time', str(timeout),
                '--max-redirs', '10', '-o', 'NUL', '-w',
                '%{http_code}|%{num_redirects}|%{url_effective}|%{ssl_verify_result}',
                url
            ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        parts = result.stdout.strip().split('|')
        if len(parts) >= 4:
            return {
                'url': url,
                'status_code': int(parts[0]) if parts[0].isdigit() else None,
                'redirect_count': int(parts[1]) if parts[1].isdigit() else 0,
                'final_url': parts[2],
                'ssl_ok': parts[3] == '0',
                'error': None
            }
        else:
            return {'url': url, 'status_code': None, 'redirect_count': 0,
                    'final_url': url, 'ssl_ok': True, 'error': result.stderr[:200]}
    except subprocess.TimeoutExpired:
        return {'url': url, 'status_code': None, 'redirect_count': 0,
                'final_url': url, 'ssl_ok': True, 'error': 'Timeout'}
    except Exception as e:
        return {'url': url, 'status_code': None, 'redirect_count': 0,
                'final_url': url, 'ssl_ok': True, 'error': str(e)}

def is_reachable(result):
    """判断检查结果是否可达"""
    code = result.get('status_code')
    if code is None:
        return False
    if 200 <= code < 300:
        return True
    if code == 405:  # Method Not Allowed 也算可达
        return True
    if 300 <= code < 400:
        return True  # 重定向
    return False

def classify_result(result):
    """分类检查结果"""
    code = result.get('status_code')
    error = result.get('error')
    if error:
        if 'Timeout' in error:
            return 'TIMEOUT'
        if 'SSL' in error or 'certificate' in error.lower():
            return 'SSL_ERROR'
        return 'CONNECTION_ERROR'
    if code is None:
        return 'NO_RESPONSE'
    if 200 <= code < 300:
        return 'OK'
    if code == 405:
        return 'OK_405'
    if code == 404:
        return '404'
    if code == 502:
        return '502'
    if code == 503:
        return '503'
    if 300 <= code < 400:
        if result.get('redirect_count', 0) >= 10:
            return 'REDIRECT_LOOP'
        return 'REDIRECT'
    if 400 <= code < 500:
        return f'CLIENT_ERROR_{code}'
    if 500 <= code < 600:
        return f'SERVER_ERROR_{code}'
    return f'UNKNOWN_{code}'

def build_url_list():
    """构建完整的 URL 检查清单"""
    urls = []
    
    # 前端 Admin 页面（通过 /admin/ 前缀访问）
    for path in ADMIN_ROUTES:
        full_path = '/admin' + path
        urls.append({
            'id': len(urls) + 1,
            'type': 'PAGE',
            'category': 'Admin',
            'url': BASE_URL + full_path,
            'path': full_path,
            'method': 'GET'
        })
    
    # 前端 H5 页面
    for path in H5_ROUTES:
        urls.append({
            'id': len(urls) + 1,
            'type': 'PAGE',
            'category': 'H5',
            'url': BASE_URL + path,
            'path': path,
            'method': 'GET'
        })
    
    # 后端 API（去重）
    backend_routes = load_and_dedup_backend_routes()
    for r in backend_routes:
        path = r['path']
        urls.append({
            'id': len(urls) + 1,
            'type': 'API',
            'category': 'Backend',
            'url': BASE_URL + path,
            'path': path,
            'method': r['method']
        })
    
    return urls

def main():
    print("=" * 60)
    print("  Noob Test - 全量链接可达性检查")
    print("=" * 60)
    print(f"项目域名: {PROJECT_DOMAIN}")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 构建 URL 列表
    print("正在构建 URL 检查清单...")
    url_list = build_url_list()
    pages = [u for u in url_list if u['type'] == 'PAGE']
    apis = [u for u in url_list if u['type'] == 'API']
    print(f"总 URL 数: {len(url_list)}")
    print(f"  - 前端页面: {len(pages)} (Admin: {len([p for p in pages if p['category']=='Admin'])}, H5: {len([p for p in pages if p['category']=='H5'])})")
    print(f"  - 后端 API: {len(apis)}")
    print()
    
    # 并行检查
    print("正在并行检查所有 URL (curl)...")
    print(f"(使用 10 线程并发，预计需要 {len(url_list) * 1.5 / 10:.0f} 秒)")
    
    results = []
    total = len(url_list)
    done = 0
    errors = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(check_url_curl, u['url']): u for u in url_list}
        for future in as_completed(future_to_url):
            u = future_to_url[future]
            try:
                result = future.result()
                result['id'] = u['id']
                result['type'] = u['type']
                result['category'] = u['category']
                result['path'] = u['path']
                result['method'] = u['method']
                result['classification'] = classify_result(result)
                result['reachable'] = is_reachable(result)
                results.append(result)
                done += 1
                if not result['reachable']:
                    errors += 1
                    print(f"  [{done}/{total}] ❌ {result['url']} → {result.get('status_code')} {result.get('error','')}")
                else:
                    print(f"  [{done}/{total}] ✅ {result['url']} → {result.get('status_code')}")
            except Exception as e:
                results.append({
                    'id': u['id'], 'type': u['type'], 'category': u['category'],
                    'url': u['url'], 'path': u['path'], 'method': u['method'],
                    'status_code': None, 'error': str(e),
                    'reachable': False, 'classification': 'EXCEPTION'
                })
                done += 1
                errors += 1
                print(f"  [{done}/{total}] ❌ {u['url']} → Exception: {e}")
    
    # 按 ID 排序
    results.sort(key=lambda x: x['id'])
    
    # 统计
    reachable = [r for r in results if r['reachable']]
    unreachable = [r for r in results if not r['reachable']]
    
    print()
    print("=" * 60)
    print("  检查完成")
    print("=" * 60)
    print(f"总 URL 数: {len(results)}")
    print(f"✅ 可达: {len(reachable)} ({len(reachable)/len(results)*100:.1f}%)")
    print(f"❌ 不可达: {len(unreachable)}")
    
    # 分类统计不可达
    class_counts = {}
    for r in unreachable:
        cls = r.get('classification', 'UNKNOWN')
        class_counts[cls] = class_counts.get(cls, 0) + 1
    for cls, cnt in sorted(class_counts.items()):
        print(f"    - {cls}: {cnt}")
    
    # 保存详细结果
    output = {
        'domain': PROJECT_DOMAIN,
        'check_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total': len(results),
        'reachable': len(reachable),
        'unreachable': len(unreachable),
        'classification_counts': class_counts,
        'results': results
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到: {OUTPUT_FILE}")
    
    return results, unreachable

if __name__ == '__main__':
    main()
