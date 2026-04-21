# -*- coding: utf-8 -*-
"""v3.1 全量链接可达性检查（外部 HTTPS）。"""
import json
import ssl
import urllib.error
import urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

URLS = [
    # ----- H5（新/老核心路由）-----
    ("H5 root", f"{BASE}/"),
    ("H5 login", f"{BASE}/login"),
    ("H5 home", f"{BASE}/home"),
    ("H5 points", f"{BASE}/points"),
    ("H5 points/detail", f"{BASE}/points/detail"),
    ("H5 points/detail?tab=exchange", f"{BASE}/points/detail?tab=exchange"),
    ("H5 points/records (legacy)", f"{BASE}/points/records"),
    ("H5 points/exchange-records (legacy)", f"{BASE}/points/exchange-records"),
    ("H5 points/mall", f"{BASE}/points/mall"),
    ("H5 points/product-detail?id=1", f"{BASE}/points/product-detail?id=1"),
    ("H5 article/1", f"{BASE}/article/1"),
    ("H5 news/1", f"{BASE}/news/1"),
    ("H5 my-coupons", f"{BASE}/my-coupons"),
    # ----- Admin -----
    ("Admin root", f"{BASE}/admin"),
    ("Admin trailing", f"{BASE}/admin/"),
    ("Admin login", f"{BASE}/admin/login"),
    # ----- 后端 API -----
    ("API health", f"{BASE}/api/health"),
    ("API home-config", f"{BASE}/api/home-config"),
    ("API home-banners", f"{BASE}/api/home-banners"),
    ("API home-menus", f"{BASE}/api/home-menus"),
    ("API content articles", f"{BASE}/api/content/articles?page=1&page_size=3"),
    ("API content news", f"{BASE}/api/content/news?page=1&page_size=3"),
    # v3.1 新接口
    ("API points/mall/items", f"{BASE}/api/points/mall/items"),
    # 详情 API（可能 404 如果没有 id=1，接受 200/404 也算可达）
    ("API points/mall/items/1", f"{BASE}/api/points/mall/items/1"),
    # Admin 专用
    ("API admin/products/services", f"{BASE}/api/admin/products/services?keyword=&page=1&page_size=20"),
]


def check(url, timeout=15):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "v31-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = resp.status
            data = resp.read(400)
            return status, data.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read(400).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return None, str(e)


def main():
    # 对 GET 受保护 API 允许 401/403（需要登录）作为"可达"
    REACHABLE = {200, 201, 204, 301, 302, 307, 308, 401, 403, 404, 405}
    results = []
    failed = []
    for name, url in URLS:
        status, body = check(url)
        ok = status in REACHABLE
        results.append({"name": name, "url": url, "status": status, "ok": ok, "body": body[:200]})
        tag = "OK" if ok else "BAD"
        print(f"[{tag}] {status} {name} -> {url}")
        if not ok:
            failed.append(name)
    with open("link_check_v31_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nSummary:")
    print(f"  total   : {len(URLS)}")
    print(f"  passed  : {len(URLS) - len(failed)}")
    print(f"  failed  : {len(failed)}")
    if failed:
        print("  failed list:")
        for n in failed:
            print(f"    - {n}")


if __name__ == "__main__":
    main()
