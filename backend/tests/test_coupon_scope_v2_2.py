"""[2026-05-02 PRD v1] 管理后台 · 优惠券「适用范围 & 类型说明」优化 - V2.2 自动化测试

覆盖：
1. 类型说明接口（GET /api/admin/coupons/type-descriptions）
2. 上限配置接口（GET /api/admin/coupons/scope-limits）
3. 商品弹窗选择器（GET /api/admin/coupons/product-picker）
   - 仅返回实物快递+到店服务，过滤 virtual
   - keyword / category_id / fulfillment_type 过滤
   - selected_ids 批量回显（含已删除/下架标记）
4. 分类树（GET /api/admin/coupons/category-tree）
5. 按 IDs 批量查分类（GET /api/admin/coupons/categories-by-ids）
6. 分类商品数统计（GET /api/admin/coupons/category-product-count）
7. 全店在售商品数（GET /api/admin/coupons/active-product-count）
8. 创建优惠券保存校验（PRD F9）：
   - scope=category 必填 scope_ids
   - scope=product 必填 scope_ids 且 ≤ 100
   - 商品 ID 必须真实存在
   - virtual 商品禁止加入适用范围
   - exclude_ids ≤ 50
   - exclude_ids 与 scope_ids（product 模式）不重叠 → 后端兜底（前端 disable）
   - exclude_ids 必须落在已选分类范围内（category 模式）
9. 编辑历史优惠券：scope_ids/exclude_ids 字符串 → 数组兼容
10. exclude_ids 在订单核销价格计算中正确生效（命中商品不参与折扣）
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import test_session
from app.models.models import (
    Coupon,
    CouponScope,
    CouponStatus,
    CouponType,
    FulfillmentType,
    Product,
    ProductCategory,
    UserCoupon,
    UserCouponStatus,
)


# ────────────────── Fixtures ──────────────────


@pytest_asyncio.fixture
async def category_tree_data():
    """构造一个 1 级 + 2 级的分类结构 + 一些商品，返回 ids dict。"""
    async with test_session() as session:
        # 1 级
        food = ProductCategory(name="食品保健", sort_order=1, level=1)
        massage = ProductCategory(name="推拿艾灸", sort_order=2, level=1)
        session.add_all([food, massage])
        await session.commit()
        await session.refresh(food)
        await session.refresh(massage)

        # 2 级
        sub_food = ProductCategory(
            name="蜂蜜茶饮", sort_order=1, level=2, parent_id=food.id,
        )
        session.add(sub_food)
        await session.commit()
        await session.refresh(sub_food)

        # 商品
        p_honey = Product(
            name="蜂蜜柚子茶 500g", category_id=sub_food.id,
            fulfillment_type=FulfillmentType.delivery,
            sale_price=39.9, stock=100, status="active",
            images=["https://cdn/honey.png"],
        )
        p_tea = Product(
            name="柠檬茶 250g", category_id=food.id,
            fulfillment_type=FulfillmentType.delivery,
            sale_price=19.9, stock=200, status="active",
            images=None,
        )
        p_massage = Product(
            name="头部按摩 30 分钟", category_id=massage.id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=98, stock=0, status="active",
            images=None,
        )
        # virtual 商品（必须被过滤）
        p_virtual = Product(
            name="在线问诊咨询券", category_id=massage.id,
            fulfillment_type=FulfillmentType.virtual,
            sale_price=50, stock=999, status="active",
        )
        # 已下架商品
        p_off = Product(
            name="已下架商品", category_id=food.id,
            fulfillment_type=FulfillmentType.delivery,
            sale_price=10, stock=0, status="inactive",
        )
        session.add_all([p_honey, p_tea, p_massage, p_virtual, p_off])
        await session.commit()
        await session.refresh(p_honey)
        await session.refresh(p_tea)
        await session.refresh(p_massage)
        await session.refresh(p_virtual)
        await session.refresh(p_off)

        return {
            "cat_food": food.id,
            "cat_massage": massage.id,
            "cat_sub_food": sub_food.id,
            "p_honey": p_honey.id,
            "p_tea": p_tea.id,
            "p_massage": p_massage.id,
            "p_virtual": p_virtual.id,
            "p_off": p_off.id,
        }


# ────────────────── 1. 类型说明接口 ──────────────────


@pytest.mark.asyncio
async def test_type_descriptions(client: AsyncClient, admin_headers):
    r = await client.get("/api/admin/coupons/type-descriptions", headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 4
    keys = {it["key"] for it in items}
    assert keys == {"full_reduction", "discount", "voucher", "free_trial"}
    for it in items:
        assert it["name"]
        assert it["icon"]
        assert it["core_rule"]
        assert it["key_fields"]
        assert it["scenarios"]
        assert it["example"]


# ────────────────── 2. 上限配置接口 ──────────────────


@pytest.mark.asyncio
async def test_scope_limits_default(client: AsyncClient, admin_headers):
    r = await client.get("/api/admin/coupons/scope-limits", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["scope_max_products"] == 100
    assert data["exclude_max_products"] == 50


# ────────────────── 3. 商品弹窗选择器 ──────────────────


@pytest.mark.asyncio
async def test_product_picker_filters_virtual(client: AsyncClient, admin_headers, category_tree_data):
    d = category_tree_data
    r = await client.get(
        "/api/admin/coupons/product-picker?fulfillment_type=all&page=1&page_size=50",
        headers=admin_headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    ids = {it["id"] for it in items}
    # virtual 商品和 inactive 商品都不应出现
    assert d["p_virtual"] not in ids
    assert d["p_off"] not in ids
    assert d["p_honey"] in ids
    assert d["p_tea"] in ids
    assert d["p_massage"] in ids


@pytest.mark.asyncio
async def test_product_picker_tab_in_store(client: AsyncClient, admin_headers, category_tree_data):
    d = category_tree_data
    r = await client.get(
        "/api/admin/coupons/product-picker?fulfillment_type=in_store",
        headers=admin_headers,
    )
    assert r.status_code == 200
    ids = {it["id"] for it in r.json()["items"]}
    assert ids == {d["p_massage"]}


@pytest.mark.asyncio
async def test_product_picker_keyword(client: AsyncClient, admin_headers, category_tree_data):
    r = await client.get(
        "/api/admin/coupons/product-picker?keyword=按摩",
        headers=admin_headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert "按摩" in items[0]["name"]


@pytest.mark.asyncio
async def test_product_picker_category_id_includes_children(
    client: AsyncClient, admin_headers, category_tree_data
):
    """category_id 命中时应包含子分类下的商品。"""
    d = category_tree_data
    r = await client.get(
        f"/api/admin/coupons/product-picker?category_id={d['cat_food']}",
        headers=admin_headers,
    )
    assert r.status_code == 200
    ids = {it["id"] for it in r.json()["items"]}
    # 食品保健（含子分类蜂蜜茶饮） → honey + tea
    assert ids == {d["p_honey"], d["p_tea"]}


@pytest.mark.asyncio
async def test_product_picker_selected_ids_with_missing_and_off_shelf(
    client: AsyncClient, admin_headers, category_tree_data
):
    """selected_ids 回显：包含已删除（999999）和已下架商品（p_off）。"""
    d = category_tree_data
    r = await client.get(
        f"/api/admin/coupons/product-picker?selected_ids={d['p_honey']},{d['p_off']},999999",
        headers=admin_headers,
    )
    assert r.status_code == 200
    sel = {it["id"]: it for it in r.json()["selected_items"]}
    assert sel[d["p_honey"]]["missing"] is False
    assert sel[d["p_honey"]]["off_shelf"] is False
    assert sel[d["p_off"]]["missing"] is False
    assert sel[d["p_off"]]["off_shelf"] is True
    assert sel[999999]["missing"] is True
    assert sel[999999]["deleted"] is True


# ────────────────── 4. 分类树 ──────────────────


@pytest.mark.asyncio
async def test_category_tree_structure(client: AsyncClient, admin_headers, category_tree_data):
    d = category_tree_data
    r = await client.get("/api/admin/coupons/category-tree", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    food = next(it for it in items if it["id"] == d["cat_food"])
    assert len(food["children"]) == 1
    assert food["children"][0]["id"] == d["cat_sub_food"]


# ────────────────── 5. 按 IDs 批量查分类 ──────────────────


@pytest.mark.asyncio
async def test_categories_by_ids_with_missing(client: AsyncClient, admin_headers, category_tree_data):
    d = category_tree_data
    r = await client.get(
        f"/api/admin/coupons/categories-by-ids?ids={d['cat_food']},999999",
        headers=admin_headers,
    )
    assert r.status_code == 200
    items = {it["id"]: it for it in r.json()["items"]}
    assert items[d["cat_food"]]["name"] == "食品保健"
    assert items[d["cat_food"]]["missing"] is False
    assert items[999999]["missing"] is True


# ────────────────── 6. 分类商品数统计 ──────────────────


@pytest.mark.asyncio
async def test_category_product_count_includes_children(
    client: AsyncClient, admin_headers, category_tree_data
):
    """选「食品保健」时，包含子分类「蜂蜜茶饮」下的商品。"""
    d = category_tree_data
    r = await client.get(
        f"/api/admin/coupons/category-product-count?category_ids={d['cat_food']}",
        headers=admin_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["category_count"] == 1
    assert data["product_count"] == 2  # honey + tea


@pytest.mark.asyncio
async def test_active_product_count(client: AsyncClient, admin_headers, category_tree_data):
    r = await client.get("/api/admin/coupons/active-product-count", headers=admin_headers)
    assert r.status_code == 200
    # active + delivery/in_store：honey + tea + massage = 3，virtual + off 不计
    assert r.json()["product_count"] == 3


# ────────────────── 7. 创建优惠券保存校验 ──────────────────


@pytest.mark.asyncio
async def test_create_scope_category_empty(client: AsyncClient, admin_headers):
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "测试券", "type": "voucher",
            "discount_value": 10, "scope": "category", "scope_ids": [],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "请至少选择 1 个分类" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_scope_product_empty(client: AsyncClient, admin_headers):
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "测试券", "type": "voucher",
            "discount_value": 10, "scope": "product", "scope_ids": [],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "请至少选择 1 个商品" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_scope_product_virtual_forbidden(
    client: AsyncClient, admin_headers, category_tree_data
):
    d = category_tree_data
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "虚拟测试", "type": "voucher",
            "discount_value": 10, "scope": "product",
            "scope_ids": [d["p_honey"], d["p_virtual"]],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "虚拟商品" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_scope_product_id_not_exist(client: AsyncClient, admin_headers):
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "测试券", "type": "voucher",
            "discount_value": 10, "scope": "product",
            "scope_ids": [999998, 999999],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "不存在或已删除" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_scope_product_over_limit(
    client: AsyncClient, admin_headers, category_tree_data
):
    """scope_ids 超过 100 时 400。"""
    d = category_tree_data
    fake_ids = [d["p_honey"]] + list(range(10000, 10101))  # 102 个
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "超限券", "type": "voucher",
            "discount_value": 10, "scope": "product",
            "scope_ids": fake_ids, "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "100" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_exclude_over_limit(
    client: AsyncClient, admin_headers, category_tree_data
):
    """exclude_ids 超过 50 时 400。"""
    d = category_tree_data
    fake_ids = list(range(20000, 20060))  # 60 个
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "排除超限", "type": "voucher",
            "discount_value": 10, "scope": "all",
            "exclude_ids": fake_ids, "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "50" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_exclude_outside_category_scope(
    client: AsyncClient, admin_headers, category_tree_data
):
    """category 模式下，排除商品必须落在已选分类范围内。"""
    d = category_tree_data
    # 选「推拿艾灸」分类，但排除「蜂蜜柚子茶」（属于食品保健子分类）→ 应失败
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "范围测试", "type": "voucher",
            "discount_value": 10, "scope": "category",
            "scope_ids": [d["cat_massage"]],
            "exclude_ids": [d["p_honey"]],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert "不在已选分类范围内" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_exclude_within_parent_category_scope_ok(
    client: AsyncClient, admin_headers, category_tree_data
):
    """category 模式下，排除商品在父分类的子分类下时应允许。"""
    d = category_tree_data
    # 选父分类「食品保健」，排除子分类下的「蜂蜜柚子茶」→ 应成功
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "父子分类测试", "type": "voucher",
            "discount_value": 10, "scope": "category",
            "scope_ids": [d["cat_food"]],
            "exclude_ids": [d["p_honey"]],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["scope"] == "category"
    assert data["scope_ids"] == [d["cat_food"]]
    assert data["exclude_ids"] == [d["p_honey"]]


@pytest.mark.asyncio
async def test_create_scope_product_clears_exclude(
    client: AsyncClient, admin_headers, category_tree_data
):
    """scope=product 时即使前端误传 exclude_ids，后端也强制清空。"""
    d = category_tree_data
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "product 自动清空 exclude", "type": "voucher",
            "discount_value": 10, "scope": "product",
            "scope_ids": [d["p_honey"], d["p_tea"]],
            "exclude_ids": [d["p_massage"]],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["scope"] == "product"
    assert sorted(data["scope_ids"]) == sorted([d["p_honey"], d["p_tea"]])
    assert data["exclude_ids"] in (None, [])


# ────────────────── 8. 编辑兼容历史字符串格式 ──────────────────


@pytest.mark.asyncio
async def test_edit_legacy_string_scope_ids(
    client: AsyncClient, admin_headers, category_tree_data
):
    """历史 scope_ids 是字符串 "1,2,3"，编辑时返回应被规范化为数组。"""
    d = category_tree_data
    # 直接用 ORM 写入历史脏数据
    async with test_session() as session:
        c = Coupon(
            name="历史脏数据券",
            type=CouponType.voucher,
            discount_value=10,
            scope=CouponScope.product,
            scope_ids=f"{d['p_honey']},{d['p_tea']}",  # 字符串
            validity_days=30,
            status=CouponStatus.active,
        )
        session.add(c)
        await session.commit()
        await session.refresh(c)
        coupon_id = c.id

    # 列表回显时自动规范为数组
    r = await client.get("/api/admin/coupons", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    target = next(it for it in items if it["id"] == coupon_id)
    assert isinstance(target["scope_ids"], list)
    assert sorted(target["scope_ids"]) == sorted([d["p_honey"], d["p_tea"]])


# ────────────────── 9. exclude_ids 在折扣计算中生效 ──────────────────


@pytest.mark.asyncio
async def test_exclude_ids_effect_on_order_discount(
    client: AsyncClient, admin_headers, auth_headers, user_token, category_tree_data
):
    """下单时 exclude_ids 命中商品不参与门槛 / 折扣计算（PRD F6 + 8.4）。

    场景：
      - 商品 honey=39.9, tea=19.9，订单 1 件 honey + 1 件 tea = 59.8
      - 优惠券：scope=all + exclude_ids=[honey] + 满 50 减 20
      - 命中后，可享券金额 = 59.8 - 39.9 = 19.9，不达 50 门槛 → 应 400
      - 改为 不排除 → 满 50 减 20 → 享 20 减
    """
    d = category_tree_data

    # 先创建一张 满 50 减 20、排除 honey 的券
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "满50减20-排除honey", "type": "full_reduction",
            "condition_amount": 50, "discount_value": 20,
            "scope": "all", "exclude_ids": [d["p_honey"]],
            "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    coupon_excl_id = r.json()["id"]

    # 再创建一张 不排除 的对照券
    r2 = await client.post(
        "/api/admin/coupons",
        json={
            "name": "满50减20-无排除", "type": "full_reduction",
            "condition_amount": 50, "discount_value": 20,
            "scope": "all", "validity_days": 30,
        },
        headers=admin_headers,
    )
    assert r2.status_code == 200
    coupon_normal_id = r2.json()["id"]

    # 给当前用户领取这两张券
    # 用户从 user_token 获取自己的 user_id
    me_resp = await client.get("/api/users/me", headers=auth_headers)
    if me_resp.status_code != 200:
        # 退而求其次，直接查 db
        from app.models.models import User
        from sqlalchemy import select
        async with test_session() as s:
            u = (await s.execute(select(User).where(User.phone == "13900000001"))).scalar_one()
            user_id = u.id
    else:
        user_id = me_resp.json().get("id") or me_resp.json().get("user", {}).get("id")
        if not user_id:
            from app.models.models import User
            from sqlalchemy import select
            async with test_session() as s:
                u = (await s.execute(select(User).where(User.phone == "13900000001"))).scalar_one()
                user_id = u.id

    async with test_session() as s:
        s.add(UserCoupon(user_id=user_id, coupon_id=coupon_excl_id, status=UserCouponStatus.unused))
        s.add(UserCoupon(user_id=user_id, coupon_id=coupon_normal_id, status=UserCouponStatus.unused))
        await s.commit()

    # 下单 1 件 honey + 1 件 tea = 59.8
    order_payload = {
        "items": [
            {"product_id": d["p_honey"], "quantity": 1},
            {"product_id": d["p_tea"], "quantity": 1},
        ],
        "payment_method": "wechat",
        "coupon_id": coupon_excl_id,
        "points_deduction": 0,
    }
    r3 = await client.post("/api/orders/unified", json=order_payload, headers=auth_headers)
    # 排除 honey 后，可享券金额 19.9 < 50，不满足门槛 → 400
    assert r3.status_code == 400, r3.text
    assert "门槛" in r3.json()["detail"] or "条件" in r3.json()["detail"]

    # 改用不排除的券 → 满足门槛 → 减 20
    order_payload["coupon_id"] = coupon_normal_id
    r4 = await client.post("/api/orders/unified", json=order_payload, headers=auth_headers)
    assert r4.status_code == 200, r4.text
    data = r4.json()
    assert abs(float(data["coupon_discount"]) - 20.0) < 0.01
    assert abs(float(data["paid_amount"]) - 39.8) < 0.01
