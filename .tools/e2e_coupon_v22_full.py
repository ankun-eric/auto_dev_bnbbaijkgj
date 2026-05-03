"""完整 E2E 测试：覆盖 PRD F1-F9 的核心保存校验。"""
import urllib.request
import urllib.error
import json
import time

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
TOKEN = None


def http(method, url, body=None):
    h = {"User-Agent": "e2e/1.0"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, headers=h, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b""


def parse(payload):
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None


passed = 0
failed = 0
results = []


def assert_test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(("OK", name, detail))
        print(f"  [OK  ] {name}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        results.append(("FAIL", name, detail))
        print(f"  [FAIL] {name} — {detail}")


# Login
print("=== 0. 登录 admin ===")
code, body = http("POST", f"{BASE}/api/admin/login",
                  body={"phone": "13800000000", "password": "admin123"})
assert code == 200, f"login failed {code} {body[:200]}"
d = parse(body) or {}
TOKEN = d.get("access_token")
print(f"  → token ok")

# F1：类型说明 4 种齐全
print("\n=== F1：类型说明 ===")
code, body = http("GET", f"{BASE}/api/admin/coupons/type-descriptions")
d = parse(body)
items = (d or {}).get("items") or []
keys = sorted(it["key"] for it in items)
assert_test("F1 类型说明返回 4 种类型", code == 200 and keys ==
            ["discount", "free_trial", "full_reduction", "voucher"],
            f"keys={keys}")
for it in items:
    has_all = all(it.get(k) for k in ("name", "icon", "core_rule", "key_fields", "scenarios", "example"))
    assert_test(f"F1 类型 {it['key']} 字段完整", has_all)

# F5/F6 上限配置接口
print("\n=== F5/F6：上限配置 ===")
code, body = http("GET", f"{BASE}/api/admin/coupons/scope-limits")
d = parse(body) or {}
assert_test("F5 scope_max_products 默认 100",
            code == 200 and d.get("scope_max_products") == 100,
            f"got={d}")
assert_test("F6 exclude_max_products 默认 50",
            code == 200 and d.get("exclude_max_products") == 50)

# F3：分类树
print("\n=== F3：分类树 ===")
code, body = http("GET", f"{BASE}/api/admin/coupons/category-tree")
d = parse(body) or {}
tree_items = d.get("items", [])
assert_test("F3 分类树成功返回（数量 > 0）", code == 200 and len(tree_items) > 0,
            f"top-level count={len(tree_items)}")

# F4：商品弹窗
print("\n=== F4：商品弹窗 ===")
code, body = http("GET",
                  f"{BASE}/api/admin/coupons/product-picker?fulfillment_type=all&page=1&page_size=5")
d = parse(body) or {}
items = d.get("items", [])
assert_test("F4 商品弹窗（全部 Tab）", code == 200 and len(items) > 0,
            f"total={d.get('total')}")
# virtual 不返回（接口强制过滤）
all_types = {it.get("fulfillment_type") for it in items}
assert_test("F4 商品弹窗 不包含 virtual",
            "virtual" not in all_types,
            f"types={all_types}")

# F8：分类商品数
print("\n=== F8：统计预览 ===")
if tree_items:
    cat_id = tree_items[0]["id"]
    code, body = http("GET",
                      f"{BASE}/api/admin/coupons/category-product-count?category_ids={cat_id}")
    d = parse(body) or {}
    assert_test("F8 分类商品数统计接口可用",
                code == 200 and "product_count" in d,
                f"got={d}")
code, body = http("GET", f"{BASE}/api/admin/coupons/active-product-count")
d = parse(body) or {}
assert_test("F8 全店在售数接口", code == 200 and "product_count" in d,
            f"got={d}")

# F2/F9：保存校验
print("\n=== F2/F9：保存校验 ===")

# F9.1: scope=category 必填
code, body = http("POST", f"{BASE}/api/admin/coupons", body={
    "name": f"E2E_test_cat_empty_{int(time.time())}",
    "type": "voucher", "discount_value": 10, "scope": "category",
    "scope_ids": [], "validity_days": 30,
})
d = parse(body) or {}
assert_test("F9 scope=category 空 scope_ids 应 400",
            code == 400 and "至少选择 1 个分类" in (d.get("detail") or ""),
            f"got code={code} detail={d.get('detail')}")

# F9.2: scope=product 必填
code, body = http("POST", f"{BASE}/api/admin/coupons", body={
    "name": f"E2E_test_prod_empty_{int(time.time())}",
    "type": "voucher", "discount_value": 10, "scope": "product",
    "scope_ids": [], "validity_days": 30,
})
d = parse(body) or {}
assert_test("F9 scope=product 空 scope_ids 应 400",
            code == 400 and "至少选择 1 个商品" in (d.get("detail") or ""),
            f"got code={code} detail={d.get('detail')}")

# F9.3: scope_ids 超 100 上限
fake_ids = list(range(900000, 900105))  # 105 个
code, body = http("POST", f"{BASE}/api/admin/coupons", body={
    "name": f"E2E_test_over_100_{int(time.time())}",
    "type": "voucher", "discount_value": 10, "scope": "product",
    "scope_ids": fake_ids, "validity_days": 30,
})
d = parse(body) or {}
assert_test("F9 scope_ids > 100 应 400",
            code == 400 and "100" in (d.get("detail") or ""),
            f"got code={code} detail={(d.get('detail') or '')[:80]}")

# F9.4: exclude_ids 超 50 上限
fake_ids = list(range(800000, 800060))  # 60 个
code, body = http("POST", f"{BASE}/api/admin/coupons", body={
    "name": f"E2E_test_excl_over_50_{int(time.time())}",
    "type": "voucher", "discount_value": 10, "scope": "all",
    "exclude_ids": fake_ids, "validity_days": 30,
})
d = parse(body) or {}
assert_test("F9 exclude_ids > 50 应 400",
            code == 400 and "50" in (d.get("detail") or ""),
            f"got code={code} detail={(d.get('detail') or '')[:80]}")

# F2/F6：scope=all + exclude_ids 正常成功
# 先取 1 个真实商品
code, body = http("GET",
                  f"{BASE}/api/admin/coupons/product-picker?fulfillment_type=all&page=1&page_size=1")
d = parse(body) or {}
items = d.get("items", [])
if items:
    pid = items[0]["id"]
    code, body = http("POST", f"{BASE}/api/admin/coupons", body={
        "name": f"E2E_test_scope_all_excl_{int(time.time())}",
        "type": "voucher", "discount_value": 5, "scope": "all",
        "exclude_ids": [pid], "validity_days": 30,
    })
    d = parse(body) or {}
    if code == 200:
        assert_test("F2 scope=all + exclude_ids 正常保存", True,
                    f"id={d.get('id')} exclude_ids={d.get('exclude_ids')}")
        # cleanup: offline
        cid = d.get("id")
        if cid:
            http("POST", f"{BASE}/api/admin/coupons/{cid}/offline",
                 body={"reason_type": "活动结束"})
    else:
        assert_test("F2 scope=all + exclude_ids 正常保存", False,
                    f"got code={code} detail={(d.get('detail') or '')[:80]}")
else:
    assert_test("F2 scope=all + exclude_ids 正常保存", False, "无可用商品")

print(f"\n=== 总计：{passed} 通过 / {failed} 失败 ===")
print("\n失败明细：")
for status, name, detail in results:
    if status == "FAIL":
        print(f"  - {name}: {detail}")
