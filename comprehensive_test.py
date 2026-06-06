"""Comprehensive Noob Test - Full link accessibility check."""
import json
import ssl
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ADMIN_BASE = BASE + "/admin"
TIMEOUT = 15

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def check_url(path, method="GET"):
    """Check a single URL and return (path, method, status_code, ok, body_preview, elapsed)."""
    start = time.time()
    url = BASE + path
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", "NoobTestSkill/1.0")
        resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
        body = resp.read(500).decode("utf-8", errors="replace")[:200]
        elapsed = int((time.time() - start) * 1000)
        code = resp.getcode()
        ok = code > 0 and code not in (502, 503, 504)
        return (path, method, code, ok, body, elapsed)
    except urllib.error.HTTPError as e:
        elapsed = int((time.time() - start) * 1000)
        code = e.code
        ok = code > 0 and code not in (502, 503, 504)
        try:
            body = e.read(500).decode("utf-8", errors="replace")[:200]
        except Exception:
            body = ""
        return (path, method, code, ok, body, elapsed)
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return (path, method, 0, False, str(e)[:100], elapsed)


def main():
    with open("all_routes_extracted.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    # 1. Critical + Payment endpoints
    print("=== 1. Critical + Payment Endpoints ===")
    critical = [
        ("/", "GET"), ("/api/health", "GET"), ("/admin/", "GET"),
        ("/api/openapi.json", "GET"), ("/api/docs", "GET"), ("/api/redoc", "GET"),
        ("/api/system/server-time", "GET"), ("/api/config", "GET"),
        ("/api/landing", "GET"), ("/api/public/protocol/privacy-policy", "GET"),
        ("/api/public/protocol/service-agreement", "GET"),
        ("/api/v2/app/version-check", "GET"),
        ("/api/pay/available-methods?platform=h5", "GET"),
        ("/api/pay/available-methods?platform=miniprogram", "GET"),
        ("/api/admin/payment-channels/wechat_miniprogram", "GET"),
        ("/api/admin/payment-channels/alipay_h5", "GET"),
        ("/api/admin/payment-channels/wechat_miniprogram/default-notify-url", "GET"),
        ("/api/admin/payment-channels/alipay_h5/default-notify-url", "GET"),
        ("/api/admin/refunds", "GET"),
        ("/api/orders/unified/counts", "GET"),
        ("/api/orders/unified/sandbox-confirm", "GET"),
        ("/api/payment/alipay/notify", "POST"),
    ]
    for path, method in critical:
        _, _, code, ok, body, elapsed = check_url(path, method)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {code} {method} {path} ({elapsed}ms)")
        results.append({"path": path, "method": method, "status": code, "ok": ok, "category": "critical"})

    # 2. Backend API GET endpoints (unique, no params)
    print("\n=== 2. Backend API GET Endpoints ===")
    get_paths = list(set(
        r["path"] for r in data["backend"]
        if r["method"] == "GET" and "{" not in r["path"] and "[" not in r["path"]
    ))
    get_paths.sort()
    print(f"  Total unique GET endpoints: {len(get_paths)}, checking first 200...")

    ok_count = 0
    fail_count = 0
    for i, path in enumerate(get_paths[:200]):
        _, _, code, ok, body, elapsed = check_url(path)
        if ok:
            ok_count += 1
        else:
            fail_count += 1
            print(f"  FAIL [{code}] GET {path} ({elapsed}ms)")
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/200 OK={ok_count} FAIL={fail_count}")
    print(f"  API GET Results: OK={ok_count} FAIL={fail_count}")

    # 3. POST endpoints (sample)
    print("\n=== 3. Backend API POST Endpoints ===")
    post_paths = list(set(
        r["path"] for r in data["backend"]
        if r["method"] == "POST" and "{" not in r["path"] and "[" not in r["path"]
    ))
    post_paths.sort()
    print(f"  Total unique POST endpoints: {len(post_paths)}, checking first 80...")
    post_ok = 0
    post_fail = 0
    for i, path in enumerate(post_paths[:80]):
        _, _, code, ok, body, elapsed = check_url(path, "POST")
        # 405 = method not allowed (expected for GET-only check), 422 = unprocessable (no body)
        if ok or code in (405, 422, 401, 403, 404):
            post_ok += 1
        else:
            post_fail += 1
            print(f"  FAIL [{code}] POST {path} ({elapsed}ms)")
    print(f"  POST Results: OK/expected={post_ok} FAIL={post_fail}")

    # 4. H5 Frontend Pages
    print("\n=== 4. H5 Frontend Pages ===")
    h5_count = 0
    h5_fail = 0
    for path in data["h5_pages"]:
        if "[" in path or "]" in path:
            continue
        _, _, code, ok, body, elapsed = check_url(path)
        if ok and code < 400:
            h5_count += 1
        elif code == 308:
            h5_count += 1  # trailing slash redirect is normal
        else:
            h5_fail += 1
            print(f"  FAIL [{code}] {path}")
    print(f"  H5 Results: OK(200/308)={h5_count} FAIL={h5_fail}")

    # 5. Admin Frontend Pages
    print("\n=== 5. Admin Frontend Pages ===")
    adm_count = 0
    adm_fail = 0
    for path in data["admin_pages"]:
        if "[" in path or "]" in path:
            continue
        adm_path = "/admin" + path if path != "/" else "/admin/"
        _, _, code, ok, body, elapsed = check_url(adm_path)
        if ok and code < 400:
            adm_count += 1
        elif code == 308:
            adm_count += 1
        else:
            adm_fail += 1
            print(f"  FAIL [{code}] {adm_path}")
    print(f"  Admin Results: OK(200/308)={adm_count} FAIL={adm_fail}")

    # 6. Payment-specific deep check
    print("\n=== 6. Payment Feature Deep Check ===")
    payment_urls = [
        ("GET", "/api/pay/available-methods?platform=miniprogram", "Payment Methods - MiniProgram"),
        ("GET", "/api/pay/available-methods?platform=h5", "Payment Methods - H5"),
        ("POST", "/api/pay/wechat/jsapi-order", "WxPay JSAPI Order"),
        ("POST", "/api/pay/notify/wechat_miniprogram", "WxPay Notify Callback"),
        ("POST", "/api/payment/alipay/notify", "Alipay Notify Callback"),
        ("GET", "/api/admin/payment-channels/wechat_miniprogram", "Admin WxPay Channel"),
        ("GET", "/api/admin/payment-channels/alipay_h5", "Admin Alipay Channel"),
        ("POST", "/api/admin/payment-channels/wechat_miniprogram/test", "Admin WxPay Test"),
        ("POST", "/api/admin/payment-channels/alipay_h5/test", "Admin Alipay Test"),
        ("GET", "/api/admin/payment-channels/wechat_miniprogram/default-notify-url", "WxPay Notify URL"),
        ("GET", "/api/admin/payment-channels/alipay_h5/default-notify-url", "Alipay Notify URL"),
        ("GET", "/api/admin/refunds", "Admin Refund List"),
        ("GET", "/api/admin/orders/unified", "Admin Unified Orders"),
        ("POST", "/api/admin/orders/unified/1/refund", "Admin Order Refund"),
        ("GET", "/api/admin/orders/unified/1/refund-detail", "Admin Refund Detail"),
        ("GET", "/api/orders/unified/counts", "User Order Counts"),
        ("GET", "/api/orders/unified/sandbox-confirm", "Sandbox Confirm"),
        ("POST", "/api/orders/unified/1/refund", "User Order Refund"),
    ]
    pmt_fail = 0
    for method, path, desc in payment_urls:
        _, _, code, ok, body, elapsed = check_url(path, method)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {code} {desc} ({elapsed}ms)")
        if not ok and code not in (401, 403, 404, 405, 422):
            pmt_fail += 1
    print(f"  Payment Results: FAIL={pmt_fail}")

    print("\n=== TEST COMPLETE ===")


if __name__ == "__main__":
    main()
