"""[2026-04-23] 部署后的全量链接可达性检查。"""
import requests
import sys

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

ENDPOINTS = [
    # 健康检查
    ("GET", f"{BASE}/api/health", (200, 301, 302), ""),
    # 关键页面（Next.js 前端 HTML）
    ("GET", f"{BASE}/", (200, 302, 307, 308), ""),
    ("GET", f"{BASE}/checkup", (200, 302, 307, 308), ""),
    ("GET", f"{BASE}/checkup/compare/select", (200, 302, 307, 308), ""),
    ("GET", f"{BASE}/checkup/trend", (200, 302, 307, 308), ""),
    ("GET", f"{BASE}/checkup/compare", (200, 302, 307, 308), ""),
    ("GET", f"{BASE}/admin/prompt-templates", (200, 302, 307, 308), ""),
    # 新 API 未鉴权应 401/403
    ("POST", f"{BASE}/api/report/interpret/start", (401, 403, 422, 400), '{"report_id":1}'),
    ("POST", f"{BASE}/api/report/compare/start", (401, 403, 422, 400), '{"member_id":1,"report_ids":[1,2]}'),
    # 下线 API 应 410 或鉴权
    ("POST", f"{BASE}/api/report/analyze", (410, 401, 403, 422), '{"report_id":1}'),
    ("GET", f"{BASE}/api/report/trend/xxx", (410, 401, 403), ""),
]


def main():
    fail = 0
    for method, url, allowed, body in ENDPOINTS:
        try:
            if method == "GET":
                r = requests.get(url, timeout=30, allow_redirects=False, verify=False)
            else:
                r = requests.post(url, data=body, timeout=30, allow_redirects=False, verify=False,
                                  headers={"Content-Type": "application/json"})
            ok = r.status_code in allowed
            tag = "OK" if ok else "FAIL"
            print(f"[{tag}] {method} {url} -> {r.status_code} (allowed={allowed})")
            if not ok:
                fail += 1
                print(f"    body: {r.text[:200]}")
        except Exception as e:
            print(f"[ERR ] {method} {url} -> {e}")
            fail += 1
    print(f"\n总计失败：{fail}/{len(ENDPOINTS)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    sys.exit(main())
