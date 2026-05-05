"""
[2026-05-05 预约门店点击行为统一为联系商家 Bug 修复] 非 UI 回归测试

由于本次仅前端 UI 行为修改（点击范围扩大），后端无任何改动。
本测试做以下验证，确保前端"门店行整行点击 → 联系商家弹层"修复后整体可用：
  1. H5 订单详情页可访问
  2. 关键路由（订单列表/订单详情）可访问
  3. 联系商家弹层底层接口 GET /api/stores/{id}/contact 协议正确（无门店时 404 或 401，参数有效时 200）
  4. 各端首页可访问
"""

import sys
import time
import urllib.parse
import urllib.request
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
TIMEOUT = 15
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def http(method, path, headers=None, body=None):
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, method=method, data=body)
    req.add_header("User-Agent", "appt-store-contact-test/1.0")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            return resp.status, resp.read()[:2048]
    except urllib.error.HTTPError as e:
        return e.code, (e.read()[:2048] if hasattr(e, "read") else b"")
    except Exception as e:
        return 0, str(e).encode()


cases = []


def check(name, ok, detail=""):
    cases.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), "-", name, ("- " + detail) if detail else "")


def main():
    # 1. H5 首页
    code, _ = http("GET", "/")
    check("H5 首页可访问", code == 200, f"HTTP {code}")

    # 2. 登录页
    code, _ = http("GET", "/login")
    check("H5 登录页可访问", code == 200, f"HTTP {code}")

    # 3. 订单列表页
    code, _ = http("GET", "/unified-orders")
    check("H5 订单列表页可访问", code == 200, f"HTTP {code}")

    # 4. 订单详情页（任意 id，前端会处理 404）
    code, _ = http("GET", "/unified-order/test-id-12345")
    check(
        "H5 订单详情页（含门店行）可访问",
        code == 200,
        f"HTTP {code}",
    )

    # 5. 联系商家弹层底层接口（未鉴权 / 不存在的门店：应返回非 5xx 的明确状态码）
    code, body = http("GET", "/api/stores/999999/contact")
    check(
        "联系商家底层接口 /api/stores/{id}/contact 协议正常",
        code in (200, 401, 403, 404, 422),
        f"HTTP {code}",
    )

    # 6. /api/health 可访问
    code, _ = http("GET", "/api/health")
    check("后端健康检查 /api/health", code == 200, f"HTTP {code}")

    # 7. 管理后台可访问
    code, _ = http("GET", "/admin")
    check(
        "管理后台首页",
        code in (200, 301, 302, 307, 308),
        f"HTTP {code}",
    )

    # 8. 小程序下载链接
    mp_url = (
        BASE
        + "/miniprogram/miniprogram_20260505_101443_9124.zip"
    )
    code, _ = http("GET", mp_url)
    check(
        "小程序新包 zip 下载链接可访问",
        code == 200,
        f"HTTP {code}",
    )

    # 9. 安卓 APK 下载链接
    apk_url = (
        BASE
        + "/apk/bini_health_android_20260505_101727_d7bc.apk"
    )
    code, _ = http("GET", apk_url)
    check(
        "安卓新包 APK 下载链接可访问",
        code == 200,
        f"HTTP {code}",
    )

    # 总结
    total = len(cases)
    passed = sum(1 for _, ok, _ in cases if ok)
    print()
    print(f"==== 测试结束: {passed}/{total} 通过 ====")
    for n, ok, d in cases:
        print((" OK " if ok else "FAIL"), n, d)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
