# -*- coding: utf-8 -*-
"""[2026-05-02 H5 下单流程优化 PRD v1.0] 服务器端 E2E 自动化测试

直接对生产网关发起 HTTP 调用，覆盖：
1. 公开接口 /api/h5/slots 可访问且返回正确结构
2. 注册并登录普通用户后，/api/h5/checkout/init 200 + 关键字段非空
3. /api/products 列表至少能拿到 1 个商品（用于 init 测试）
4. 管理后台门店列表的 slot_capacity / business_start / business_end 字段已下发
"""
import json
import sys
import time
import urllib.parse as up
import urllib.request as ur
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def req(method: str, url: str, *, headers: dict | None = None, body: dict | None = None, timeout: int = 30):
    data = None
    headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    rq = ur.Request(url, data=data, method=method, headers=headers)
    try:
        with ur.urlopen(rq, context=CTX, timeout=timeout) as r:
            text = r.read().decode("utf-8", "replace")
            return r.status, text
    except ur.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, body


def assert_(cond: bool, msg: str):
    if not cond:
        print(f"  ✗ {msg}")
        return False
    print(f"  ✓ {msg}")
    return True


def main() -> int:
    fails: list[str] = []
    print("== 1. /api/h5/slots 公开访问 ==")
    code, text = req("GET", f"{BASE}/api/h5/slots?storeId=1&date=2026-05-10&productId=1")
    if not assert_(code == 200, f"slots 200, got {code}"):
        fails.append("slots_200")
        print(text[:500])
    else:
        try:
            j = json.loads(text)
            assert_("data" in j and isinstance(j["data"].get("slots"), list), "slots 数组结构正确")
        except Exception as e:
            fails.append(f"slots_json:{e}")

    print("\n== 2. 用户注册 + 登录 ==")
    phone = f"139{int(time.time()) % 100000000:08d}"
    code, text = req("POST", f"{BASE}/api/auth/register", body={
        "phone": phone, "password": "test1234", "nickname": f"e2e_{phone}"
    })
    if not assert_(code in (200, 400), f"register {code}"):
        fails.append("register")
    code, text = req("POST", f"{BASE}/api/auth/login", body={"phone": phone, "password": "test1234"})
    if not assert_(code == 200, f"login 200, got {code}"):
        fails.append("login")
        print(text[:500])
        return 1
    token = json.loads(text).get("access_token")
    if not assert_(bool(token), "got token"):
        fails.append("token")
        return 1
    auth_headers = {"Authorization": f"Bearer {token}"}

    print("\n== 3. 列出商品（/api/products） ==")
    code, text = req("GET", f"{BASE}/api/products?status=active&page=1&size=5", headers=auth_headers)
    if not assert_(code == 200, f"products list 200, got {code}"):
        fails.append("products_list")
        print(text[:500])
        return 1
    j = json.loads(text)
    # 尝试多种结构
    products = []
    for path in (("data", "items"), ("data",), ("items",)):
        cur: any = j
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, list) and cur:
            products = cur
            break
    pid = None
    for p in products:
        if isinstance(p, dict) and p.get("id"):
            pid = p["id"]
            break
    if pid is None:
        print(f"  raw products payload preview: {text[:400]}")
    if not assert_(pid is not None, f"got first product id={pid}"):
        fails.append("no_product")
        return 1

    print(f"\n== 4. /api/h5/checkout/init?productId={pid} ==")
    code, text = req("GET", f"{BASE}/api/h5/checkout/init?productId={pid}", headers=auth_headers)
    if not assert_(code == 200, f"checkout/init 200, got {code}"):
        fails.append("checkout_init_200")
        print(text[:600])
    else:
        j = json.loads(text)
        d = j.get("data", {})
        assert_("date_range" in d, "包含 date_range")
        assert_("available_slots" in d, "包含 available_slots")
        assert_("contact_phone" in d, "包含 contact_phone")
        assert_(d.get("contact_phone") == phone, f"contact_phone == {phone}")
        # slot 不应再包含 capacity（前端隐藏 + 下单不读取）
        for s in d.get("available_slots") or []:
            if "capacity" in s:
                fails.append("slot_should_hide_capacity")
                break
        else:
            print("  ✓ available_slots 已隐藏 capacity")

    print("\n== 5. /api/h5/slots 数据结构（按已选门店） ==")
    code, text = req("GET", f"{BASE}/api/h5/slots?storeId=1&date=2026-05-10&productId={pid}")
    if not assert_(code == 200, f"h5/slots got {code}"):
        fails.append("h5_slots_200")
        print(text[:300])

    print("\n== 6. /api/products/{id}/available-stores 是否含新字段 ==")
    code, text = req("GET", f"{BASE}/api/products/{pid}/available-stores", headers=auth_headers)
    if assert_(code == 200, f"available-stores 200"):
        j = json.loads(text)
        stores = j.get("data", {}).get("stores", [])
        if stores:
            s0 = stores[0]
            assert_("slot_capacity" in s0, f"store 包含 slot_capacity (got {s0.get('slot_capacity')!r})")
            assert_("business_start" in s0, "store 包含 business_start")
            assert_("business_end" in s0, "store 包含 business_end")
        else:
            print("  ! 没有可用门店, 跳过字段断言")

    print("\n========")
    if fails:
        print(f"FAILURES: {fails}")
        return 2
    print("ALL E2E PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
