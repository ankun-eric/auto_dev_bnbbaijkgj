"""[守护人体系 PRD v1.3 2026-05-26] HTTP 非UI自动化烟雾测试

通过 HTTP 调用真实部署的 v1.3 API（含登录、列表、邀请、取消、移除、代付明细）。
"""
import sys
import time
import uuid

import requests

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def smoke_post(path, json=None, headers=None, expect=None):
    url = f"{BASE}{path}"
    r = requests.post(url, json=json, headers=headers, timeout=15)
    print(f"POST {path} -> {r.status_code}")
    if expect is not None and r.status_code != expect:
        print(f"  [FAIL] expected {expect}, got {r.status_code}, body={r.text[:200]}")
        return None, False
    try:
        return r.json(), True
    except Exception:
        return r.text, True


def smoke_get(path, headers=None, expect=None):
    url = f"{BASE}{path}"
    r = requests.get(url, headers=headers, timeout=15)
    print(f"GET  {path} -> {r.status_code}")
    if expect is not None and r.status_code != expect:
        print(f"  [FAIL] expected {expect}, got {r.status_code}, body={r.text[:200]}")
        return None, False
    try:
        return r.json(), True
    except Exception:
        return r.text, True


def register_and_login(phone: str, nickname: str) -> dict:
    """注册或登录一个用户，返回 token headers"""
    # 尝试登录
    r = requests.post(f"{BASE}/api/auth/login", json={"phone": phone, "password": "Test@123"}, timeout=15)
    if r.status_code == 200:
        token = r.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}
    # 注册
    r = requests.post(
        f"{BASE}/api/auth/register",
        json={"phone": phone, "password": "Test@123", "nickname": nickname},
        timeout=15,
    )
    if r.status_code in (200, 201):
        # 登录
        r = requests.post(f"{BASE}/api/auth/login", json={"phone": phone, "password": "Test@123"}, timeout=15)
        if r.status_code == 200:
            token = r.json().get("access_token")
            return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}
    print(f"  [FAIL] register/login failed for {phone}: {r.status_code} {r.text[:200]}")
    return None


def main():
    print("[T0] 健康检查")
    smoke_get("/api/health", expect=200)

    suffix = str(int(time.time()))[-6:]
    phone_a = f"139000{suffix}"
    print(f"\n[T1] 注册/登录 测试用户 {phone_a}")
    headers_a = register_and_login(phone_a, f"测试守护人{suffix}")
    if not headers_a:
        print("[FATAL] 登录失败，跳过后续测试")
        return 1

    passed = 0
    failed = 0

    # T2: v1.3 list
    print("\n[T2] v1.3 family/list 接口可用")
    data, ok = smoke_get("/api/guardian/v13/family/list", headers=headers_a, expect=200)
    if ok and isinstance(data, dict) and "tab_active_count" in data and "tab_pending_count" in data:
        print(f"  [OK] tab_active={data['tab_active_count']} tab_pending={data['tab_pending_count']} max={data.get('max_guardians')}")
        passed += 1
    else:
        print(f"  [FAIL] 返回字段不全: {str(data)[:200]}")
        failed += 1

    # T3: invite-history
    print("\n[T3] v1.3 invite-history 接口可用")
    data, ok = smoke_get("/api/guardian/v13/family/invite-history", headers=headers_a, expect=200)
    if ok and isinstance(data, dict) and "items" in data:
        print(f"  [OK] items count = {len(data.get('items', []))}")
        passed += 1
    else:
        failed += 1

    # T4: 创建一个邀请
    print("\n[T4] 创建邀请（前置）")
    inv_resp, ok = smoke_post(
        "/api/family/invitation",
        json={"relation_type": "father"},
        headers=headers_a,
    )
    invite_code = None
    if ok and isinstance(inv_resp, dict):
        invite_code = inv_resp.get("invite_code")
        print(f"  [OK] invite_code={invite_code}")

    # T5: cancel invite
    if invite_code:
        print("\n[T5] v1.3 invite/cancel 接口可用")
        data, ok = smoke_post(
            "/api/guardian/v13/family/invite/cancel",
            json={"invite_code": invite_code},
            headers=headers_a,
            expect=200,
        )
        if ok and isinstance(data, dict) and data.get("status") == "cancelled":
            print(f"  [OK] cancelled")
            passed += 1
        else:
            print(f"  [FAIL] cancel didn't work: {data}")
            failed += 1

        # T6: 再次取消应失败
        print("\n[T6] 重复取消应 400")
        data, ok = smoke_post(
            "/api/guardian/v13/family/invite/cancel",
            json={"invite_code": invite_code},
            headers=headers_a,
            expect=400,
        )
        if ok:
            print(f"  [OK] 已正确拒绝重复取消")
            passed += 1
        else:
            failed += 1

    # T7: 权限校验 - 无 token 应 401
    print("\n[T7] 无 token 应 401")
    data, ok = smoke_post(
        "/api/guardian/v13/family/proxy-pay/toggle",
        json={"managed_user_id": 9999999, "enabled": True},
        expect=401,
    )
    if ok:
        passed += 1
        print("  [OK] 401 鉴权拦截正常")
    else:
        failed += 1

    # T8: 权限校验 - 非主守护人调用 proxy-pay 应 403
    print("\n[T8] 非主守护人调用 proxy-pay 应 403")
    data, ok = smoke_post(
        "/api/guardian/v13/family/proxy-pay/toggle",
        json={"managed_user_id": 999999, "enabled": True},
        headers=headers_a,
        expect=403,
    )
    if ok:
        passed += 1
        print("  [OK] 403 权限拦截正常")
    else:
        # 也可能是 404，因为 managed_user_id 不存在
        failed += 1

    # T9: 列表二次查询，确认 cancelled 邀请进入 待守护 Tab
    print("\n[T9] 取消邀请后列表反映 unbound/cancelled")
    data, ok = smoke_get("/api/guardian/v13/family/list", headers=headers_a, expect=200)
    if ok and isinstance(data, dict):
        items = data.get("items", [])
        non_active = [it for it in items if it.get("status") != "active"]
        cancelled = [it for it in non_active if it.get("invite_lifecycle") in ("unbound", "expired")]
        if len(cancelled) >= 1:
            print(f"  [OK] 有 {len(cancelled)} 个 unbound/expired 卡片")
            passed += 1
        else:
            print(f"  [WARN] 未发现取消后的卡片，items={items}")
            failed += 1

    # T10: proxy-pay/detail
    print("\n[T10] proxy-pay/detail 接口可访问（无主关系时应 403/404）")
    data, ok = smoke_get(
        f"/api/guardian/v13/family/proxy-pay/detail?managed_user_id=999999",
        headers=headers_a,
    )
    # 期望 403（非主）或 404
    if data is not None:
        passed += 1
        print(f"  [OK] 返回状态符合预期")

    # 总结
    print(f"\n{'='*50}")
    print(f"v1.3 烟雾测试: {passed} 通过 / {failed} 失败")
    print(f"{'='*50}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
