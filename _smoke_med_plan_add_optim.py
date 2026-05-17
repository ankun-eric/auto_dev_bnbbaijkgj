"""[PRD-MED-PLAN-ADD-OPTIM-V1] 公网 smoke 测试

- 前端路由 /ai-home/medication-plans/new 200
- 后端新接口 /api/medication-library/suggest 401（鉴权生效，未传 token）
- 鉴权后接口能正常返回（注册 + 登录 + 调接口）
"""
import json
import secrets
import sys
import urllib.parse
from typing import Optional

import urllib3
urllib3.disable_warnings()

import requests

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

def hr(t):
    print("\n=== " + t + " ===")


def check_url(url, expect, allow_redirects=False, hdrs=None) -> bool:
    try:
        r = requests.get(url, headers=hdrs or {}, timeout=20, verify=False,
                         allow_redirects=allow_redirects)
        ok = (r.status_code == expect) if isinstance(expect, int) else (r.status_code in expect)
        print(f"  GET {url[:100]} -> {r.status_code} {'OK' if ok else 'FAIL (expect ' + str(expect) + ')'}")
        return ok
    except Exception as e:
        print(f"  GET {url[:100]} -> EXC: {e}")
        return False


def main():
    failures = []

    hr("Frontend routes")
    if not check_url(f"{BASE}/ai-home/medication-plans/new", (200, 301, 302, 307, 308)):
        failures.append("frontend new")
    if not check_url(f"{BASE}/ai-home/medication-plans", (200, 301, 302, 307, 308)):
        failures.append("frontend list")

    hr("Backend new endpoint unauth")
    if not check_url(f"{BASE}/api/medication-library/suggest?q=test", (401, 403)):
        failures.append("backend suggest unauth")

    hr("Backend new endpoint authed")
    # 注册 + 登录新用户
    phone = "139" + secrets.token_hex(4)[:8]
    pwd = "Test123!"
    reg = requests.post(f"{BASE}/api/auth/register",
                        json={"phone": phone, "password": pwd, "nickname": "smoke"},
                        timeout=20, verify=False)
    print("  register:", reg.status_code, reg.text[:200])
    login = requests.post(f"{BASE}/api/auth/login",
                          json={"phone": phone, "password": pwd},
                          timeout=20, verify=False)
    print("  login:", login.status_code)
    token = (login.json() or {}).get("access_token")
    if not token:
        failures.append("login failed")
    else:
        hdrs = {"Authorization": f"Bearer {token}"}
        # 1) q < 2 字 → 空 items
        r = requests.get(f"{BASE}/api/medication-library/suggest?q=b",
                         headers=hdrs, timeout=20, verify=False)
        print("  suggest(q=b):", r.status_code, r.text[:200])
        if r.status_code != 200:
            failures.append("suggest q<2")
        else:
            body = r.json()
            if body.get("items"):
                failures.append("suggest q<2 should be empty")
        # 2) q >= 2 字 → 200（可能空 items，因为库可能无匹配）
        r = requests.get(f"{BASE}/api/medication-library/suggest?q=阿莫&limit=6",
                         headers=hdrs, timeout=20, verify=False)
        print("  suggest(q=阿莫):", r.status_code, r.text[:300])
        if r.status_code != 200:
            failures.append("suggest q>=2")
        # 3) limit 上限
        r = requests.get(f"{BASE}/api/medication-library/suggest?q=药&limit=20",
                         headers=hdrs, timeout=20, verify=False)
        print("  suggest(q=药 limit=20):", r.status_code, str(r.text)[:200])
        if r.status_code != 200:
            failures.append("suggest q>=2 limit")

    hr("Summary")
    if failures:
        print("FAILED:", failures)
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
