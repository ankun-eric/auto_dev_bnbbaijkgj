"""
Link reachability check for order-bugfix deploy (commit 208e390).
Uses Python requests to verify all 11 links from the real external HTTPS domain.
"""
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("[err] requests not installed; run: pip install requests")
    sys.exit(2)

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

# (name, path, expected_set, note)
LINKS = [
    ("api-health",           f"{BASE}/api/health",                          {200, 201, 202, 204}, "期望 2xx"),
    ("api-orders-old",       f"{BASE}/api/orders",                          {404},                "老接口已下线"),
    ("api-admin-orders-old", f"{BASE}/api/admin/orders",                    {404, 401},           "老接口已下线"),
    ("api-unified-counts",   f"{BASE}/api/orders/unified/counts",           {401, 200},           "未带 token 401 / 或 200"),
    ("h5-home",              f"{BASE}/",                                    {200, 301, 302, 304}, "H5 首页"),
    ("h5-orders-old",        f"{BASE}/orders",                              {404},                "老 H5 页面已删"),
    ("h5-unified-orders",    f"{BASE}/unified-orders",                      {200, 304},           "统一订单页"),
    ("h5-refund-list",       f"{BASE}/refund-list",                         {200, 304},           "退款列表页"),
    ("admin-home",           f"{BASE}/admin/",                              {200, 301, 302, 304}, "管理后台首页"),
    ("admin-orders-old",     f"{BASE}/admin/orders",                        {404},                "管理后台老订单页已删"),
    ("admin-product-orders", f"{BASE}/admin/product-system/orders",         {200, 301, 302, 304}, "管理后台新订单页"),
]


def check_one(name, url, expected_set, note):
    try:
        r = requests.get(url, allow_redirects=True, timeout=20, verify=True)
        redirects = len(r.history)
        redirect_chain = " -> ".join([h.url for h in r.history] + [r.url]) if r.history else r.url
        status = r.status_code
        passed = status in expected_set
        return {
            "name": name,
            "url": url,
            "status": status,
            "redirects": redirects,
            "final_url": r.url,
            "redirect_chain": redirect_chain,
            "expected": sorted(expected_set),
            "pass": passed,
            "note": note,
            "error": None,
            "body_snippet": r.text[:200] if not passed else "",
        }
    except Exception as e:
        return {
            "name": name,
            "url": url,
            "status": None,
            "redirects": None,
            "final_url": None,
            "redirect_chain": None,
            "expected": sorted(expected_set),
            "pass": False,
            "note": note,
            "error": str(e),
            "body_snippet": "",
        }


def main():
    print(f"[link-check] BASE = {BASE}")
    print(f"[link-check] total {len(LINKS)} urls")
    print()

    results = []
    for (name, url, expected_set, note) in LINKS:
        r = check_one(name, url, expected_set, note)
        mark = "OK  " if r["pass"] else "FAIL"
        extra = f"redir={r['redirects']}" if r["status"] is not None else f"err={r['error']}"
        print(f"[{mark}] {r['status']!s:>5} {extra:<12} {name:<26} {url}")
        if not r["pass"] and r["error"] is None:
            print(f"        expected={r['expected']}  final={r['final_url']}")
            if r["body_snippet"]:
                print(f"        body[:200]={r['body_snippet']!r}")
        results.append(r)

    total = len(results)
    ok = sum(1 for r in results if r["pass"])
    print()
    print("=" * 70)
    print(f"Summary: {ok}/{total} pass")

    out = {
        "base": BASE,
        "commit": "208e390",
        "total": total,
        "pass_count": ok,
        "fail_count": total - ok,
        "results": results,
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_link_check_orderbugfix.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {out_path}")

    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
