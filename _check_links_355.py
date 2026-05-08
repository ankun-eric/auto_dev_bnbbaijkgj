#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[355] 部署后链接可达性检查"""
import urllib.request
import urllib.error
import ssl
import time

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

# 关键链接清单
LINKS = [
    # 后端 API
    ("API", "GET", f"{BASE}/api/health", "健康检查"),
    ("API", "GET", f"{BASE}/api/docs", "API 文档(Swagger)"),
    ("API", "GET", f"{BASE}/api/redoc", "API 文档(Redoc)"),
    ("API", "GET", f"{BASE}/api/openapi.json", "OpenAPI 规范"),
    # 管理后台
    ("ADMIN", "GET", f"{BASE}/admin/", "管理后台首页"),
    ("ADMIN", "GET", f"{BASE}/admin/login", "管理后台登录"),
    # H5 用户端
    ("H5", "GET", f"{BASE}/", "H5 首页"),
]


def check(method, url, timeout=15):
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, method=method, headers={"User-Agent": "checker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            code = resp.status
            location = resp.headers.get("Location", "")
            body_len = len(resp.read(4096))
            return code, location, body_len, ""
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "") if e.headers else ""
        return e.code, loc, 0, ""
    except Exception as e:
        return -1, "", 0, str(e)


def main():
    print("=" * 80)
    print(f"[355] 部署后全量链接可达性检查")
    print(f"基础 URL: {BASE}")
    print("=" * 80)

    results = []
    for typ, method, url, desc in LINKS:
        code, loc, blen, err = check(method, url)
        # 可达判定：2xx, 3xx 重定向到合理位置, 405, 422
        ok = False
        reason = ""
        if 200 <= code < 300:
            ok = True
            reason = f"{code} OK"
        elif code in (301, 302, 307, 308):
            # 检查 Location 是否合理（不出项目基础URL路径）
            if loc.startswith(BASE) or loc.startswith("/autodev/6b099ed3"):
                ok = True
                reason = f"{code} → {loc}"
            else:
                ok = False
                reason = f"{code} → {loc} (异常重定向)"
        elif code in (405, 422):
            ok = True
            reason = f"{code}（路径可达，方法/参数限制）"
        elif code == 404:
            ok = False
            reason = "404"
        elif code == 502:
            ok = False
            reason = "502 Bad Gateway"
        elif code == -1:
            ok = False
            reason = f"网络错误: {err[:80]}"
        else:
            ok = False
            reason = f"HTTP {code}"

        flag = "✅" if ok else "❌"
        print(f"{flag} [{typ:5}] {method:4} {url}")
        print(f"      → {reason}  ({desc})")
        results.append((ok, typ, url, reason))

    print("=" * 80)
    okN = sum(1 for r in results if r[0])
    total = len(results)
    print(f"汇总：{okN}/{total} 可达，{total - okN} 不可达")
    print("=" * 80)

    if okN < total:
        print("\n不可达链接：")
        for ok, typ, url, reason in results:
            if not ok:
                print(f"  - [{typ}] {url}  →  {reason}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
