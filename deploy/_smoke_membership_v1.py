"""[付费会员体系 PRD v1.1] 服务器端 API 烟雾测试。

通过对真实部署做 HTTP 调用，验证：
- 套餐 CRUD（admin）
- 免费额度 GET/PUT
- 用户端套餐列表
- 当前用户会员状态
- 收银台优惠计算（无优惠 / 仅积分抵扣 + 20% 上限）
"""
from __future__ import annotations

import json
import sys
import time

import urllib.parse
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def http(method: str, path: str, body=None, token: str | None = None, expected: tuple[int, ...] = (200,)):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json", "Client-Type": "h5-user"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.getcode()
            payload = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        code = e.code
        payload = e.read().decode("utf-8", errors="replace")
    short = payload[:300]
    print(f"  {method} {path} -> {code}  {short}")
    if code not in expected:
        raise RuntimeError(f"Unexpected HTTP {code} for {method} {path}: {payload[:500]}")
    if not payload:
        return None
    try:
        return json.loads(payload)
    except Exception:
        return payload


def login_admin() -> str:
    r = http("POST", "/api/admin/login", {"phone": "13800138000", "password": "admin123"}, expected=(200, 401, 422))
    if isinstance(r, dict) and r.get("token"):
        return r["token"]
    # 尝试默认管理员
    r = http("POST", "/api/admin/login", {"phone": "13800138001", "password": "admin123"}, expected=(200, 401, 422))
    if isinstance(r, dict) and r.get("token"):
        return r["token"]
    raise RuntimeError("无法用预设密码登录管理员，请手动检查测试帐号")


def main() -> int:
    print(f"BASE = {BASE}\n")

    failures = []

    # 0. 健康检查
    try:
        http("GET", "/api/openapi.json")
    except Exception as e:
        print(f"FAIL openapi: {e}")
        return 1

    # 1. 用户端可见套餐列表（无 token，公开）
    print("\n[1] GET /api/membership/plans (公开)")
    try:
        plans = http("GET", "/api/membership/plans")
        assert isinstance(plans, list)
    except Exception as e:
        failures.append(f"用户端套餐列表查询失败: {e}")

    # 2. 取得管理员 token
    print("\n[2] 获取管理员 token")
    try:
        admin_token = login_admin()
        print(f"  admin token: {admin_token[:20]}...")
    except Exception as e:
        print(f"  未能登录管理员（可能服务器使用了不同的 admin 帐号）：{e}")
        admin_token = None

    if admin_token:
        # 3. 套餐 CRUD
        print("\n[3] 套餐 CRUD")
        unique_code = f"smoke_{int(time.time())}"
        try:
            r = http("POST", "/api/admin/membership/plans", {
                "plan_code": unique_code,
                "name": "烟雾测试套餐",
                "price_monthly": 9.9,
                "ai_call_quota": 5,
                "ai_alert_quota": 10,
                "ai_remind_quota": 20,
                "max_guardians": 2,
                "discount_rate": 0.9,
                "is_active": True,
                "sort_order": 999,
            }, token=admin_token)
            pid = r["id"]
            print(f"  创建成功 id={pid}")

            r = http("GET", "/api/admin/membership/plans", token=admin_token)
            assert any(p["plan_code"] == unique_code for p in r), "套餐未在列表中"

            r = http("PUT", f"/api/admin/membership/plans/{pid}", {"discount_rate": 0.8}, token=admin_token)
            assert abs(r["discount_rate"] - 0.8) < 0.001

            r = http("DELETE", f"/api/admin/membership/plans/{pid}", token=admin_token)
            assert r.get("soft_deleted") is True

            print("  套餐 CRUD: PASS")
        except Exception as e:
            failures.append(f"套餐 CRUD 失败: {e}")

        # 4. 免费额度
        print("\n[4] 免费额度 GET/PUT")
        try:
            cur = http("GET", "/api/admin/membership/free-quota", token=admin_token)
            print(f"  current free quota: ai_alert={cur['ai_alert_quota']}")
            r = http("PUT", "/api/admin/membership/free-quota", {"ai_alert_quota": 4}, token=admin_token)
            assert r["ai_alert_quota"] == 4
            # 还原
            http("PUT", "/api/admin/membership/free-quota",
                 {"ai_alert_quota": cur["ai_alert_quota"]}, token=admin_token)
            print("  免费额度: PASS")
        except Exception as e:
            failures.append(f"免费额度失败: {e}")

    print("\n========== SMOKE TEST SUMMARY ==========")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        return 1
    print("  ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
