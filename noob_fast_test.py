"""
Noob Test 快速链接检查 - 重点 URL
"""
import subprocess, json, re, ssl, socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
TIMEOUT = 8
MAX_WORKERS = 20
OUTPUT = "noob_fast_results.json"

# ===== 精简 URL 清单 =====
URLS = [
    # === 重点：脑力游戏 ===
    ("H5_BRAIN", f"https://{DOMAIN}/brain-game"),
    ("API_BRAIN_REGIONS", f"https://{DOMAIN}/api/brain-game/regions"),
    ("API_BRAIN_TREE", f"https://{DOMAIN}/api/brain-game/regions/tree"),
    ("API_BRAIN_RANKINGS", f"https://{DOMAIN}/api/brain-game/rankings"),
    ("API_BRAIN_MINE", f"https://{DOMAIN}/api/brain-game/challenges/mine"),
    ("API_BRAIN_USER", f"https://{DOMAIN}/api/brain-game/user-info"),
    ("API_BRAIN_WX", f"https://{DOMAIN}/api/brain-game/wechat-config?url=https://t.cn"),
    ("API_BRAIN_SCORES", f"https://{DOMAIN}/api/brain-game/scores"),
    ("API_BRAIN_CHALLENGES", f"https://{DOMAIN}/api/brain-game/challenges"),
    
    # === 核心页面 ===
    ("H5_HOME", f"https://{DOMAIN}/"),
    ("H5_LOGIN", f"https://{DOMAIN}/login"),
    ("ADMIN_HOME", f"https://{DOMAIN}/admin/"),
    
    # === 核心 API ===
    ("API_HEALTH", f"https://{DOMAIN}/api/health"),
    ("API_SERVER_TIME", f"https://{DOMAIN}/api/system/server-time"),
    ("API_AUTH_ME", f"https://{DOMAIN}/api/auth/me"),
    ("API_HOME_CONFIG", f"https://{DOMAIN}/api/home-config"),
    ("API_DOCS", f"https://{DOMAIN}/api/docs"),
    ("API_OPENAPI", f"https://{DOMAIN}/api/openapi.json"),
    
    # === 之前失败的重新检查 ===
    ("RETRY_CARE_HOME", f"https://{DOMAIN}/care-home"),
    ("RETRY_PRIVACY", f"https://{DOMAIN}/legal/privacy-policy"),
    ("RETRY_M_ORDER", f"https://{DOMAIN}/merchant/m/orders/1"),
    ("RETRY_RPT_HIST", f"https://{DOMAIN}/report-history"),
    ("RETRY_RPT_HIST1", f"https://{DOMAIN}/report-history/1"),
    ("RETRY_REVIEW", f"https://{DOMAIN}/review/1"),
    ("RETRY_ADMIN_EMAIL", f"https://{DOMAIN}/admin/email-notify"),
    ("RETRY_ADMIN_GUARD", f"https://{DOMAIN}/admin/guardian-relations"),
    ("RETRY_ADMIN_OCR", f"https://{DOMAIN}/admin/ocr-config"),
    ("RETRY_ADMIN_ORDERS", f"https://{DOMAIN}/admin/orders"),
    ("RETRY_ADMIN_APPT", f"https://{DOMAIN}/admin/product-system/appointment-forms"),
    ("RETRY_ADMIN_SETTINGS", f"https://{DOMAIN}/admin/settings"),
    ("RETRY_ADMIN_SMS", f"https://{DOMAIN}/admin/sms"),
    ("RETRY_API_GUARDIAN", f"https://{DOMAIN}/api/family/guardians/1"),
    
    # === H5 关键页面抽样 ===
    ("H5_AI_HOME", f"https://{DOMAIN}/ai-home"),
    ("H5_FAMILY", f"https://{DOMAIN}/family"),
    ("H5_HEALTH_PROFILE", f"https://{DOMAIN}/health-profile"),
    ("H5_POINTS", f"https://{DOMAIN}/points"),
    ("H5_PRODUCTS", f"https://{DOMAIN}/products"),
    ("H5_MEDICAL", f"https://{DOMAIN}/medical-records"),
    ("H5_TCM", f"https://{DOMAIN}/tcm"),
    ("H5_CHECKUP", f"https://{DOMAIN}/checkup"),
    ("H5_GLUCOSE", f"https://{DOMAIN}/glucose"),
    ("H5_CARDS", f"https://{DOMAIN}/cards"),
    ("H5_WELCOME", f"https://{DOMAIN}/welcome-mode"),
    ("H5_SAFETY", f"https://{DOMAIN}/care-safety-rope"),
    ("H5_HOME_SAFETY", f"https://{DOMAIN}/home-safety"),
    ("H5_DEVICES", f"https://{DOMAIN}/devices"),
    ("H5_SETTINGS", f"https://{DOMAIN}/settings"),
    
    # === Admin 页面抽样 ===
    ("ADMIN_DASHBOARD", f"https://{DOMAIN}/admin/dashboard"),
    ("ADMIN_USERS", f"https://{DOMAIN}/admin/users"),
    ("ADMIN_AI_CONFIG", f"https://{DOMAIN}/admin/ai-config"),
    ("ADMIN_FB", f"https://{DOMAIN}/admin/function-buttons"),
    ("ADMIN_KNOWLEDGE", f"https://{DOMAIN}/admin/knowledge"),
    ("ADMIN_MERCHANT", f"https://{DOMAIN}/admin/merchant/stores"),
    ("ADMIN_PAYMENT", f"https://{DOMAIN}/admin/payment-config"),
    ("ADMIN_COS", f"https://{DOMAIN}/admin/cos-config"),
    
    # === 更多 API ===
    ("API_FAMILY_MEMBERS", f"https://{DOMAIN}/api/family/members"),
    ("API_CHAT_SESSIONS", f"https://{DOMAIN}/api/chat/sessions"),
    ("API_POINTS", f"https://{DOMAIN}/api/points/balance"),
    ("API_COUPONS", f"https://{DOMAIN}/api/coupons/mine"),
    ("API_SEARCH", f"https://{DOMAIN}/api/search/hot"),
    ("API_NOTICES", f"https://{DOMAIN}/api/notices/active"),
    ("API_MERCHANT", f"https://{DOMAIN}/api/merchant/stores"),
    ("API_PRODUCTS", f"https://{DOMAIN}/api/products"),
    ("API_MESSAGES", f"https://{DOMAIN}/api/messages/unread-count"),
    ("API_MEMBERSHIP", f"https://{DOMAIN}/api/membership/plans"),
    ("API_TCM_CONFIG", f"https://{DOMAIN}/api/tcm/config"),
    ("API_DEVICES", f"https://{DOMAIN}/api/devices/catalog"),
    ("API_GLUCOSE", f"https://{DOMAIN}/api/glucose-v1/latest"),
    ("API_SAFETY", f"https://{DOMAIN}/api/safety-rope/status"),
    ("API_CARE", f"https://{DOMAIN}/api/care-v1/home/welcome"),
    ("API_MED_TODAY", f"https://{DOMAIN}/api/medication/today"),
    ("API_ADMIN_DASH", f"https://{DOMAIN}/api/admin/dashboard"),
    ("API_ADMIN_USERS", f"https://{DOMAIN}/api/admin/users"),
    ("API_H5_BOTTOM", f"https://{DOMAIN}/api/h5/bottom-nav"),
    ("API_H5_THEME", f"https://{DOMAIN}/api/h5/active-theme"),
    ("API_REGIONS_V2", f"https://{DOMAIN}/api/v2/regions"),
    ("API_H5_CHECKOUT", f"https://{DOMAIN}/api/h5/checkout/init"),
]

def check(url):
    cmd = ["curl", "-Is", "--connect-timeout", "5", "--max-time", str(TIMEOUT), "-L", "--max-redirs", "10", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT+5)
        out = r.stdout + r.stderr
        codes = re.findall(r'HTTP/\S+\s+(\d{3})', out)
        if not codes:
            return (0, 0, "NO_RESPONSE" if r.returncode != 0 else "NO_HTTP", "")
        final = int(codes[-1])
        redirects = sum(1 for c in codes if c.startswith('30'))
        if redirects >= 10:
            return (final, redirects, "REDIRECT_LOOP", str(codes))
        if final < 400 or final == 405:
            return (final, redirects, "OK", str(codes))
        return (final, redirects, "HTTP_ERR", str(codes))
    except subprocess.TimeoutExpired:
        return (0, 0, "TIMEOUT", "")
    except Exception as e:
        return (0, 0, "ERROR", str(e)[:100])

def check_ssl():
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((DOMAIN, 443), timeout=5) as s:
            with ctx.wrap_socket(s, server_hostname=DOMAIN) as ss:
                c = ss.getpeercert()
                return {"ok": True, "expires": c.get('notAfter',''), "cn": dict(x[0] for x in c.get('subject',[])).get('commonName','')}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def main():
    print("="*70)
    print(f"  Noob Fast Test | {DOMAIN}")
    print("="*70)
    
    ssl = check_ssl()
    print(f"  SSL: {ssl}")
    
    entries = [(i+1, len(URLS), label, url) for i, (label, url) in enumerate(URLS)]
    results = []
    
    def worker(entry):
        i, total, label, url = entry
        code, redirs, status, detail = check(url)
        r = {"url": url, "label": label, "http": code, "redirects": redirs, "status": status, "detail": detail}
        icon = "OK" if status == "OK" else "!!"
        print(f"  [{i:3d}/{total}] {icon} {code:3d} r{redirs} | {label:30s}")
        return r
    
    print(f"\n  检查 {len(URLS)} 个 URL（{MAX_WORKERS} 并发）...\n")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for f in as_completed([ex.submit(worker, e) for e in entries]):
            results.append(f.result())
    
    # Stats
    ok = [r for r in results if r["status"] == "OK" and r["http"] < 400]
    api405 = [r for r in results if r["status"] == "OK" and r["http"] == 405]
    bad = [r for r in results if r["status"] in ("HTTP_ERR", "REDIRECT_LOOP")]
    err = [r for r in results if r["status"] in ("NO_RESPONSE", "NO_HTTP", "TIMEOUT", "ERROR")]
    
    print(f"\n{'='*70}")
    print(f"  结果统计")
    print(f"{'='*70}")
    print(f"  ✅ 可达 (2xx/3xx): {len(ok)}")
    print(f"  ⚠️  API 405 (需认证): {len(api405)}")
    print(f"  ❌ 不可达: {len(bad)}")
    print(f"  💥 连接失败/超时: {len(err)}")
    
    if bad:
        print(f"\n  --- 不可达 ---")
        for r in bad:
            print(f"  HTTP {r['http']} | {r['url']} | {r['detail']}")
    
    if err:
        print(f"\n  --- 连接失败 ---")
        for r in err:
            print(f"  {r['status']} | {r['url']}")
    
    out = {"domain": DOMAIN, "ssl": ssl, "total": len(URLS),
           "ok": len(ok), "api_405": len(api405), "bad": len(bad), "err": len(err),
           "reachable": ok, "api_405_list": api405, "unreachable": bad, "errors": err}
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  结果已写入 {OUTPUT}")
    return out

if __name__ == "__main__":
    main()
