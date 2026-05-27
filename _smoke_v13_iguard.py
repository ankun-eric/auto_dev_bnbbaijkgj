"""
[Bug 修复 我守护的人 v13 恢复] 服务器端非UI自动化烟雾测试

测试目标：通过 https 公网入口验证：
1) /health-profile/i-guard 前端页面 200 (允许 308 重定向到末尾 /)
2) v13 6 个接口在未授权访问时返回 401（路由可达且需鉴权）
"""
import urllib.request
import urllib.error
import json
import sys

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def probe(method: str, path: str, expected: list[int], body: dict | None = None):
    url = f"{BASE}{path}"
    try:
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        print(f"❌ {method:5} {path}  -> ERROR: {e}")
        return False

    ok = code in expected
    sym = "✅" if ok else "❌"
    print(f"{sym} {method:5} {path}  -> HTTP {code}  (expected={expected})")
    return ok


def main():
    print(f"=== v13 i-guard 恢复烟雾测试 @ {BASE} ===\n")

    cases = [
        # 前端页面（已登录会重定向、未登录会跳登录页；任何 200/30x/40x 均说明路由可达不 502）
        ("GET", "/health-profile/i-guard", [200, 301, 302, 303, 307, 308, 401]),
        # v13 6 个接口（未鉴权应返回 401）
        ("GET", "/api/guardian/v13/family/list", [401]),
        ("GET", "/api/guardian/v13/family/invite-history", [401]),
        ("POST", "/api/guardian/v13/family/proxy-pay/toggle", [401, 422]),
        ("GET", "/api/guardian/v13/family/proxy-pay/detail", [401]),
        ("POST", "/api/guardian/v13/family/invite/cancel", [401, 422]),
        ("POST", "/api/guardian/v13/family/remove", [401, 422]),
    ]

    fails = 0
    for m, p, exp in cases:
        body = {} if m == "POST" else None
        if not probe(m, p, exp, body=body):
            fails += 1

    print(f"\n=== 完成：失败 {fails} / {len(cases)} ===")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
