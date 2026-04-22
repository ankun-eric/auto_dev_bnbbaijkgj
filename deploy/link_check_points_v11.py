# -*- coding: utf-8 -*-
"""积分商城 v1.1 的全链路链接验证（公网 HTTPS）。

检查：
- h5-web 用户端页面（积分商城 / 兑换记录 / 详情）
- admin-web 页面（登录 / 积分商城）
- 后端核心接口（用户端 list tab=all/exchangeable、健康检查）
- admin 后台商品管理相关接口：list / change-logs 需登录，跳过；作为占位仅看 401/200

不可达自动输出不通过列表与状态码。
"""
import json
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

LINKS = [
    # 基础
    f"{BASE}/api/health",
    # 用户端 H5
    f"{BASE}/points/mall",
    f"{BASE}/points/exchange-records",
    f"{BASE}/points/detail",
    f"{BASE}/points/product-detail?id=1",
    # admin-web
    f"{BASE}/admin/",
    f"{BASE}/admin/login",
    # 后端用户端列表（两个 tab）
    f"{BASE}/api/points/mall?tab=all&page=1&page_size=20",
    f"{BASE}/api/points/mall?tab=exchangeable&page=1&page_size=20",
    # 后端 admin 接口（未登录预期 401/403，也是"可达"）
    f"{BASE}/api/admin/points/mall",
    f"{BASE}/api/admin/points/mall/1/change-logs",
]


def check(url: str):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "v11-check"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def main():
    results = []
    bad = []
    for u in LINKS:
        code, err = check(u)
        ok = (code is not None) and (200 <= code < 500)  # admin 未登录的 401/403 视为可达
        results.append({"url": u, "code": code, "err": err, "ok": ok})
        if not ok:
            bad.append(u)
        print(f"{code if code else 'ERR':<4} {u}  {err or ''}")

    with open("link_check_points_v11.json", "w", encoding="utf-8") as f:
        json.dump({"base": BASE, "results": results, "bad": bad}, f, ensure_ascii=False, indent=2)

    print("\n================")
    print(f"total={len(results)} bad={len(bad)}")
    if bad:
        print("UNREACHABLE:")
        for u in bad:
            print("  " + u)


if __name__ == "__main__":
    main()
