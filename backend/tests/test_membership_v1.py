"""[付费会员体系 PRD v1.1] 自动化测试 [已被 PRD v1.0 终稿对齐取代]

⚠️ 本测试文件中的字段（plan_code/ai_remind_quota/ai_alert_quota/ai_call_quota/
max_guardians/benefits_desc/price_monthly/price_yearly）已于 2026-05-26
PRD v1.0 终稿对齐时全部物理删除。本文件整体跳过执行；新的字段对齐测试位于
test_member_center_prd_v1_aligned.py。
"""

from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.skip(reason="v1.1 老字段已被 PRD v1.0 终稿对齐物理删除；新测试见 test_member_center_prd_v1_aligned.py")
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.models.models import PointsRecord, PointsType, Product, ProductCategory, FulfillmentType, ProductStatus


# ──────────────── helpers ────────────────


async def _create_category() -> int:
    async with test_session() as s:
        cat = ProductCategory(name="测试分类", sort_order=0)
        s.add(cat)
        await s.flush()
        cid = cat.id
        await s.commit()
        return cid


async def _create_product(
    sale_price: float = 100.0,
    is_member_discount_eligible: bool = False,
    points_deductible: bool = False,
    points_exchangeable: bool = False,
) -> int:
    cid = await _create_category()
    async with test_session() as s:
        p = Product(
            name="测试商品",
            category_id=cid,
            fulfillment_type=FulfillmentType.virtual,
            sale_price=sale_price,
            stock=10,
            status=ProductStatus.active,
            is_member_discount_eligible=is_member_discount_eligible,
            points_deductible=points_deductible,
            points_exchangeable=points_exchangeable,
        )
        s.add(p)
        await s.flush()
        pid = p.id
        await s.commit()
        return pid


async def _add_points(user_phone: str, points: int) -> None:
    """给指定用户加积分"""
    from app.models.models import User
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == user_phone))).scalar_one()
        s.add(PointsRecord(
            user_id=u.id,
            points_type=PointsType.income,
            points=points,
            source="test_seed",
        ))
        await s.commit()


# ──────────────── 1. 后台套餐 CRUD ────────────────


@pytest.mark.asyncio
async def test_admin_plan_crud(client: AsyncClient, admin_headers: dict):
    # 初始空
    r = await client.get("/api/admin/membership/plans", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []

    # 创建
    payload = {
        "plan_code": "guardian",
        "name": "守护版",
        "price_monthly": 19.9,
        "price_yearly": 199.0,
        "ai_call_quota": 30,
        "ai_alert_quota": 10,
        "ai_remind_quota": 50,
        "max_guardians": 2,
        "discount_rate": 0.9,
        "benefits_desc": "守护版基础权益",
        "is_active": True,
        "sort_order": 1,
    }
    r = await client.post("/api/admin/membership/plans", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["plan_code"] == "guardian"
    assert plan["discount_rate"] == 0.9
    pid = plan["id"]

    # 重复 plan_code 报错
    r = await client.post("/api/admin/membership/plans", json=payload, headers=admin_headers)
    assert r.status_code == 400

    # 获取列表
    r = await client.get("/api/admin/membership/plans", headers=admin_headers)
    assert len(r.json()) == 1

    # 更新
    r = await client.put(f"/api/admin/membership/plans/{pid}", json={"name": "守护版 PLUS", "discount_rate": 0.85}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "守护版 PLUS"
    assert r.json()["discount_rate"] == 0.85

    # 软下线
    r = await client.delete(f"/api/admin/membership/plans/{pid}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["soft_deleted"] is True

    # 再次列表，include_inactive 默认 True 仍可看到
    r = await client.get("/api/admin/membership/plans?include_inactive=true", headers=admin_headers)
    assert len(r.json()) == 1
    assert r.json()[0]["is_active"] is False


@pytest.mark.asyncio
async def test_admin_free_quota(client: AsyncClient, admin_headers: dict):
    # 首次 GET 自动创建默认行
    r = await client.get("/api/admin/membership/free-quota", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1

    # 更新部分字段
    r = await client.put("/api/admin/membership/free-quota", json={"ai_alert_quota": 5, "max_guardians": 2}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["ai_alert_quota"] == 5
    assert r.json()["max_guardians"] == 2


# ──────────────── 2. 用户端套餐与订阅 ────────────────


async def _create_active_plan(client: AsyncClient, admin_headers: dict, **overrides):
    payload = {
        "plan_code": "guardian",
        "name": "守护版",
        "price_monthly": 19.9,
        "price_yearly": 199.0,
        "ai_call_quota": 30,
        "ai_alert_quota": 10,
        "ai_remind_quota": 50,
        "max_guardians": 2,
        "discount_rate": 0.9,
        "is_active": True,
        "sort_order": 0,
    }
    payload.update(overrides)
    r = await client.post("/api/admin/membership/plans", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_user_plans_visible_only_active(client: AsyncClient, admin_headers: dict):
    await _create_active_plan(client, admin_headers, plan_code="g", name="守护版")
    await _create_active_plan(client, admin_headers, plan_code="f", name="家庭版", is_active=False)
    r = await client.get("/api/membership/plans")
    assert r.status_code == 200
    plans = r.json()
    assert len(plans) == 1
    assert plans[0]["plan_code"] == "g"


@pytest.mark.asyncio
async def test_membership_me_default_free(client: AsyncClient, auth_headers: dict, admin_headers: dict):
    # 设置免费额度
    await client.put("/api/admin/membership/free-quota", json={"ai_alert_quota": 3, "max_guardians": 1}, headers=admin_headers)
    r = await client.get("/api/membership/me", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_paid_member"] is False
    assert body["discount_rate"] == 1.0
    assert body["ai_alert_quota"] == 3


@pytest.mark.asyncio
async def test_user_subscribe_and_cancel(client: AsyncClient, auth_headers: dict, admin_headers: dict):
    plan = await _create_active_plan(client, admin_headers)
    r = await client.post("/api/membership/subscribe", json={"plan_id": plan["id"], "billing_cycle": "monthly"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "active"
    assert body["plan_name"] == "守护版"

    # 当前会员状态应为付费会员
    r = await client.get("/api/membership/me", headers=auth_headers)
    assert r.json()["is_paid_member"] is True
    assert r.json()["discount_rate"] == 0.9

    # 取消订阅
    r = await client.post("/api/membership/cancel", headers=auth_headers)
    assert r.status_code == 200

    # 再次查询恢复免费会员
    r = await client.get("/api/membership/me", headers=auth_headers)
    assert r.json()["is_paid_member"] is False


# ──────────────── 3. 收银台优惠计算 ────────────────


@pytest.mark.asyncio
async def test_calc_discount_no_options(client: AsyncClient, auth_headers: dict):
    """商品两个开关都关 → 无可用优惠 → 推荐 none"""
    pid = await _create_product(sale_price=100.0)
    r = await client.post(
        "/api/membership/calculate-discount",
        json={"product_id": pid, "quantity": 1, "user_points": 0},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recommended"] == "none"
    assert body["original_price"] == 100.0
    assert len(body["options"]) == 1
    assert body["options"][0]["type"] == "none"
    assert body["options"][0]["final_price"] == 100.0


@pytest.mark.asyncio
async def test_calc_discount_member_only(client: AsyncClient, auth_headers: dict, admin_headers: dict):
    """仅会员折扣可用：用户为付费会员、商品 is_member_discount_eligible=true"""
    plan = await _create_active_plan(client, admin_headers, discount_rate=0.8)
    await client.post("/api/membership/subscribe", json={"plan_id": plan["id"], "billing_cycle": "monthly"}, headers=auth_headers)
    pid = await _create_product(sale_price=200.0, is_member_discount_eligible=True, points_deductible=False)
    r = await client.post(
        "/api/membership/calculate-discount",
        json={"product_id": pid, "quantity": 1, "user_points": 100000},
        headers=auth_headers,
    )
    body = r.json()
    assert body["recommended"] == "member_discount"
    md = next(o for o in body["options"] if o["type"] == "member_discount")
    assert md["final_price"] == 160.0  # 200 * 0.8
    assert md["discount_amount"] == 40.0
    # 不应出现 points_deduction（商品未开 points_deductible）
    assert all(o["type"] != "points_deduction" for o in body["options"])


@pytest.mark.asyncio
async def test_calc_discount_points_only_with_20pct_cap(client: AsyncClient, auth_headers: dict):
    """仅积分抵扣可用 + 20% 上限封顶"""
    pid = await _create_product(sale_price=100.0, points_deductible=True)
    # 用户 5000 积分 ≈ 50 元，但 100 元订单上限 20% = 20 元
    r = await client.post(
        "/api/membership/calculate-discount",
        json={"product_id": pid, "quantity": 1, "user_points": 5000},
        headers=auth_headers,
    )
    body = r.json()
    assert body["recommended"] == "points_deduction"
    pd = next(o for o in body["options"] if o["type"] == "points_deduction")
    assert pd["discount_amount"] == 20.0  # 上限封顶
    assert pd["final_price"] == 80.0
    assert pd["use_points"] == 2000  # 20 元 / 0.01


@pytest.mark.asyncio
async def test_calc_discount_points_below_cap(client: AsyncClient, auth_headers: dict):
    """积分余额不足 20% 上限：按实际余额折抵"""
    pid = await _create_product(sale_price=100.0, points_deductible=True)
    # 用户 500 积分 = 5 元（低于 20 元上限）
    r = await client.post(
        "/api/membership/calculate-discount",
        json={"product_id": pid, "quantity": 1, "user_points": 500},
        headers=auth_headers,
    )
    body = r.json()
    pd = next(o for o in body["options"] if o["type"] == "points_deduction")
    assert pd["discount_amount"] == 5.0
    assert pd["final_price"] == 95.0
    assert pd["use_points"] == 500


@pytest.mark.asyncio
async def test_calc_discount_either_or(client: AsyncClient, auth_headers: dict, admin_headers: dict):
    """二选一：会员折扣 vs 积分抵扣，推荐力度更大者"""
    # 会员折扣 8 折 → 100 元 → 抵扣 20 元
    # 积分抵扣 20% 上限 = 20 元，与会员折扣相当
    # 这里用 5 折让会员折扣明显胜出
    plan = await _create_active_plan(client, admin_headers, discount_rate=0.5)
    await client.post("/api/membership/subscribe", json={"plan_id": plan["id"], "billing_cycle": "monthly"}, headers=auth_headers)
    pid = await _create_product(
        sale_price=100.0,
        is_member_discount_eligible=True,
        points_deductible=True,
    )
    r = await client.post(
        "/api/membership/calculate-discount",
        json={"product_id": pid, "quantity": 1, "user_points": 5000},
        headers=auth_headers,
    )
    body = r.json()
    # 会员折扣抵扣 50 元，积分抵扣最多 20 元 → 推荐 member_discount
    assert body["recommended"] == "member_discount"
    types = sorted([o["type"] for o in body["options"]])
    assert types == ["member_discount", "points_deduction"]
    md = next(o for o in body["options"] if o["type"] == "member_discount")
    pd = next(o for o in body["options"] if o["type"] == "points_deduction")
    assert md["discount_amount"] == 50.0
    assert pd["discount_amount"] == 20.0
    # 不能叠加：两者 final_price 不应等于 (100 - 50 - 20) = 30
    assert md["final_price"] != 30.0
    assert pd["final_price"] != 30.0


@pytest.mark.asyncio
async def test_calc_discount_quantity(client: AsyncClient, auth_headers: dict):
    """数量不为 1 时按 unit_price * quantity 计算原价与上限"""
    pid = await _create_product(sale_price=50.0, points_deductible=True)
    # 数量 4 → 总价 200 元 → 20% 上限 = 40 元
    r = await client.post(
        "/api/membership/calculate-discount",
        json={"product_id": pid, "quantity": 4, "user_points": 100000},
        headers=auth_headers,
    )
    body = r.json()
    assert body["original_price"] == 200.0
    pd = next(o for o in body["options"] if o["type"] == "points_deduction")
    assert pd["discount_amount"] == 40.0


# ──────────────── 4. 商品编辑页 is_member_discount_eligible 字段 ────────────────


@pytest.mark.asyncio
async def test_product_member_discount_field_create_and_update(client: AsyncClient, admin_headers: dict):
    """商品 CRUD 时 is_member_discount_eligible 字段贯通：建库默认 false → 创建时 true → 编辑切换 → 详情读出"""
    cid = await _create_category()
    payload = {
        "name": "测试 PRD v1.1 商品",
        "category_id": cid,
        "fulfillment_type": "virtual",
        "sale_price": 99.0,
        "stock": 10,
        "is_member_discount_eligible": True,
        "points_deductible": True,
        "points_exchangeable": False,
        "appointment_mode": "none",
        "redeem_count": 1,
    }
    r = await client.post("/api/admin/products", json=payload, headers=admin_headers)
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    r = await client.get(f"/api/admin/products/{pid}/detail", headers=admin_headers)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["is_member_discount_eligible"] is True
    assert detail["points_deductible"] is True

    # 关掉会员折扣开关
    r = await client.put(f"/api/admin/products/{pid}", json={"is_member_discount_eligible": False}, headers=admin_headers)
    assert r.status_code == 200, r.text

    r = await client.get(f"/api/admin/products/{pid}/detail", headers=admin_headers)
    assert r.json()["is_member_discount_eligible"] is False
    # points_deductible 仍保留
    assert r.json()["points_deductible"] is True


# ──────────────── 5. 旧"积分会员等级"API @deprecated 验证 ────────────────


@pytest.mark.asyncio
async def test_legacy_member_levels_api_marked_deprecated(client: AsyncClient):
    """[PRD v1.1] 旧"积分会员等级"API 应在 OpenAPI schema 中标记为 deprecated=True，
    但路由本身仍保留，以兼容前端历史调用。"""
    # FastAPI app 自定义 openapi_url=/api/openapi.json
    r = await client.get("/api/openapi.json")
    assert r.status_code == 200, r.text
    schema = r.json()
    paths = schema.get("paths", {})

    # 后台 4 个端点
    admin_paths = [
        ("/api/admin/points/levels", "get"),
        ("/api/admin/points/levels", "post"),
        ("/api/admin/points/levels/{level_id}", "put"),
        ("/api/admin/points/levels/{level_id}", "delete"),
    ]
    for path, method in admin_paths:
        spec = paths.get(path, {}).get(method)
        assert spec is not None, f"{method.upper()} {path} 必须存在（保留兼容）"
        assert spec.get("deprecated") is True, f"{method.upper()} {path} 必须标记 deprecated=True"

    # 用户端兼容只读端点
    user_spec = paths.get("/api/points/level", {}).get("get")
    assert user_spec is not None
    assert user_spec.get("deprecated") is True


@pytest.mark.asyncio
async def test_legacy_member_levels_api_still_callable(client: AsyncClient, admin_headers: dict):
    """旧 API 虽然 deprecated，但仍可正常调用（保留兼容期）。"""
    r = await client.get("/api/admin/points/levels", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert "items" in r.json()


# ──────────────── 6. 单笔最多抵扣 20% 上限 ────────────────


@pytest.mark.asyncio
async def test_points_deduct_capped_at_20pct(client: AsyncClient, auth_headers: dict):
    """[PRD v1.1 § 五] 积分抵扣单笔不得超过订单金额的 20%。

    场景：商品 100 元，用户有 10000 积分（=100 元），最多只能抵扣 20 元（20%）。
    """
    pid = await _create_product(sale_price=100.0, points_deductible=True)
    r = await client.post(
        "/api/membership/calculate-discount",
        json={"product_id": pid, "quantity": 1, "user_points": 10000},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    pd = next((o for o in body["options"] if o["type"] == "points_deduction"), None)
    assert pd is not None
    # 20% 上限 = 20 元，对应 2000 积分
    assert pd["discount_amount"] == 20.0
    assert pd["use_points"] == 2000


# ──────────────── 7. 套餐购买/续费禁止积分抵扣 ────────────────


@pytest.mark.asyncio
async def test_subscribe_membership_cannot_use_points(client: AsyncClient, auth_headers: dict, admin_headers: dict):
    """[PRD v1.1 § 九] 套餐购买/续费业务路径不接受积分抵扣字段，
    即使用户积分充足，订阅金额也不会被积分抵扣。"""
    plan = await _create_active_plan(client, admin_headers, discount_rate=0.9, price_monthly=29.9)

    # 即使用户提交积分抵扣字段，订阅接口也只看 plan_id / billing_cycle
    r = await client.post(
        "/api/membership/subscribe",
        json={"plan_id": plan["id"], "billing_cycle": "monthly", "points_deduction": 99999},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    sub = r.json()
    # 实付金额必须等于套餐月度价（不被积分扣减）
    assert float(sub.get("plan_id")) == float(plan["id"])
    # 用 /me 验证：到期时间、套餐均按原价订阅，没有被积分抵扣
    me_r = await client.get("/api/membership/me", headers=auth_headers)
    me = me_r.json()
    assert me["is_paid_member"] is True
    assert me["plan_id"] == plan["id"]
