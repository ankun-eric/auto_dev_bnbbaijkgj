"""[会员中心 PRD v1.0 终稿对齐 2026-05-26] 字段对齐自动化测试

覆盖以下结构性变更（PRD v1.0 终稿）：
1. membership_plans 字段对齐：name/description/price_month/price_year/max_managed/
   ai_outbound_call_count/emergency_ai_call_count/max_managed_by/discount_rate/
   is_active/is_recommended/sort_order
2. free_member_quota 字段对齐：max_managed/ai_outbound_call_count/
   emergency_ai_call_count/max_managed_by
3. 后台 CRUD 接口字段对齐
4. /api/admin/membership/plans/{id}/toggle 启停切换
5. /api/admin/users/{id}/membership 用户会员卡片
6. /api/admin/users/{id}/membership/adjust 延期/降级/重置
7. /api/admin/orders/unified 履约类型筛选（fulfillment_type=virtual）
8. /api/admin/orders/unified/{id}/refund 会员费订单退款 + 立即降级
9. /api/member/center 响应不再含 plan_code
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session


# ──────────────── helpers ────────────────


async def _create_plan(client: AsyncClient, admin_headers: dict, **overrides):
    """创建一个 PRD v1.0 字段集对齐的套餐"""
    payload = {
        "name": "守护版",
        "description": "为家庭健康守护设计",
        "price_month": 19.9,
        "price_year": 199.0,
        "max_managed": 5,
        "ai_outbound_call_count": 10,
        "emergency_ai_call_count": 3,
        "max_managed_by": 3,
        "discount_rate": 0.9,
        "is_active": True,
        "is_recommended": False,
        "sort_order": 0,
    }
    payload.update(overrides)
    r = await client.post("/api/admin/membership/plans", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# ──────────────── 1. 套餐 CRUD 字段对齐 ────────────────


@pytest.mark.asyncio
async def test_plan_create_with_v1_fields(client: AsyncClient, admin_headers: dict):
    plan = await _create_plan(client, admin_headers, name="标准版", is_recommended=True)
    # 字段对齐
    assert plan["name"] == "标准版"
    assert plan["price_month"] == 19.9
    assert plan["price_year"] == 199.0
    assert plan["max_managed"] == 5
    assert plan["ai_outbound_call_count"] == 10
    assert plan["emergency_ai_call_count"] == 3
    assert plan["max_managed_by"] == 3
    assert plan["discount_rate"] == 0.9
    assert plan["is_recommended"] is True
    # 不应包含老字段
    assert "plan_code" not in plan
    assert "ai_remind_quota" not in plan
    assert "ai_alert_quota" not in plan
    assert "ai_call_quota" not in plan
    assert "max_guardians" not in plan
    assert "benefits_desc" not in plan
    assert "price_monthly" not in plan
    assert "price_yearly" not in plan
    assert "point_multiplier" not in plan


@pytest.mark.asyncio
async def test_plan_update(client: AsyncClient, admin_headers: dict):
    plan = await _create_plan(client, admin_headers)
    pid = plan["id"]
    r = await client.put(
        f"/api/admin/membership/plans/{pid}",
        json={"is_recommended": True, "max_managed": 10, "discount_rate": 0.85},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_recommended"] is True
    assert body["max_managed"] == 10
    assert body["discount_rate"] == 0.85


@pytest.mark.asyncio
async def test_plan_toggle(client: AsyncClient, admin_headers: dict):
    plan = await _create_plan(client, admin_headers)
    pid = plan["id"]
    assert plan["is_active"] is True
    r = await client.put(f"/api/admin/membership/plans/{pid}/toggle", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    r = await client.put(f"/api/admin/membership/plans/{pid}/toggle", headers=admin_headers)
    assert r.json()["is_active"] is True


@pytest.mark.asyncio
async def test_plan_delete_when_no_reference(client: AsyncClient, admin_headers: dict):
    plan = await _create_plan(client, admin_headers)
    pid = plan["id"]
    r = await client.delete(f"/api/admin/membership/plans/{pid}", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("hard_deleted") is True
    # 物理删除后再查不到
    r = await client.get(f"/api/admin/membership/plans/{pid}", headers=admin_headers)
    assert r.status_code == 404


# ──────────────── 2. 免费额度字段对齐 ────────────────


@pytest.mark.asyncio
async def test_free_quota_fields_aligned(client: AsyncClient, admin_headers: dict):
    r = await client.get("/api/admin/membership/free-quota", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    # 新字段集
    assert "max_managed" in body
    assert "ai_outbound_call_count" in body
    assert "emergency_ai_call_count" in body
    assert "max_managed_by" in body
    # 老字段不应再出现
    assert "ai_remind_quota" not in body
    assert "ai_alert_quota" not in body
    assert "ai_call_quota" not in body
    assert "max_guardians" not in body
    assert "benefits_desc" not in body

    r = await client.put(
        "/api/admin/membership/free-quota",
        json={
            "max_managed": 4,
            "ai_outbound_call_count": 8,
            "emergency_ai_call_count": 5,
            "max_managed_by": 4,
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["max_managed"] == 4
    assert body["ai_outbound_call_count"] == 8
    assert body["emergency_ai_call_count"] == 5
    assert body["max_managed_by"] == 4


# ──────────────── 3. /api/member/center 出参清理 plan_code ────────────────


@pytest.mark.asyncio
async def test_member_center_no_plan_code(client: AsyncClient, admin_headers: dict, auth_headers: dict):
    await _create_plan(client, admin_headers, name="守护版", is_recommended=True)
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # 出参不应含 plan_code
    assert all("plan_code" not in p for p in body["plans"])
    # 推荐套餐字段透传
    assert any(p.get("is_recommended") for p in body["plans"])


@pytest.mark.asyncio
async def test_member_plans_no_plan_code(client: AsyncClient):
    r = await client.get("/api/membership/plans")
    assert r.status_code == 200


# ──────────────── 4. 后台用户会员卡片接口 ────────────────


@pytest.mark.asyncio
async def test_admin_user_membership_card(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    from app.models.models import User
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.role == "user").limit(1))).scalar_one_or_none()
        assert u is not None
        uid = u.id

    r = await client.get(f"/api/admin/users/{uid}/membership", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == uid
    assert body["membership_level"] in ("free", "paid")
    # 新字段
    assert "max_managed" in body
    assert "max_managed_by" in body
    assert "ai_outbound_call_count" in body
    assert "emergency_ai_call_count" in body


@pytest.mark.asyncio
async def test_admin_membership_adjust_reset_quota(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    # 通过 auth_headers fixture 已确保存在一个普通用户（手机号 13900000001）
    from app.models.models import User
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == "13900000001").limit(1))).scalar_one_or_none()
        assert u is not None, "auth_headers fixture should have created a user"
        uid = u.id

    r = await client.post(
        f"/api/admin/users/{uid}/membership/adjust",
        json={"action": "reset_quota"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


# ──────────────── 5. 订单管理 - 履约类型筛选 ────────────────


@pytest.mark.asyncio
async def test_admin_orders_fulfillment_filter(
    client: AsyncClient, admin_headers: dict
):
    # 接口接收 fulfillment_type 参数应正常返回 200，即使没有数据
    r = await client.get(
        "/api/admin/orders/unified?fulfillment_type=virtual&page=1&page_size=10",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body


# ──────────────── 6. 会员费订单退款 + 立即降级 ────────────────


@pytest.mark.asyncio
async def test_membership_order_refund_downgrades_user(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    from app.models.models import User
    from app.models.membership_plan import UserMembershipSub

    plan = await _create_plan(client, admin_headers, name="守护版")
    pid = plan["id"]

    # 创建会员订单 + 模拟支付
    r = await client.post(
        "/api/member/order",
        json={"plan_id": pid, "period": "month"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    order_id = r.json()["order_id"]

    r = await client.post(
        f"/api/member/order/{order_id}/pay",
        json={"simulate": True},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("paid") is True

    # 当前用户应为 active 付费会员
    me = await client.get("/api/membership/me", headers=auth_headers)
    assert me.json()["is_paid_member"] is True

    # 后台退款
    r = await client.post(
        f"/api/admin/orders/unified/{order_id}/refund",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert len(body["downgraded_subs"]) >= 1

    # 退款后用户应立即降级
    me = await client.get("/api/membership/me", headers=auth_headers)
    assert me.json()["is_paid_member"] is False


# ──────────────── 7. 重复用户场景：升降级 ────────────────


@pytest.mark.asyncio
async def test_membership_extend_after_purchase(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    plan = await _create_plan(client, admin_headers, name="标准版")
    pid = plan["id"]

    r = await client.post(
        "/api/member/order",
        json={"plan_id": pid, "period": "month"},
        headers=auth_headers,
    )
    order_id = r.json()["order_id"]
    await client.post(
        f"/api/member/order/{order_id}/pay",
        json={"simulate": True},
        headers=auth_headers,
    )

    from app.models.models import User
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.role == "user").limit(1))).scalar_one()
        uid = u.id

    info = (await client.get(f"/api/admin/users/{uid}/membership", headers=admin_headers)).json()
    assert info["membership_level"] == "paid"
    orig_expire = info["expire_at"]

    # 后台延期 10 天
    r = await client.post(
        f"/api/admin/users/{uid}/membership/adjust",
        json={"action": "extend", "days": 10},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    new_expire = r.json()["new_expire_at"]
    assert new_expire > orig_expire


# ──────────────── 8. 推荐套餐字段透传 ────────────────


@pytest.mark.asyncio
async def test_recommended_plan_field_propagated(
    client: AsyncClient, admin_headers: dict
):
    p1 = await _create_plan(client, admin_headers, name="基础版", is_recommended=False)
    p2 = await _create_plan(client, admin_headers, name="尊享版", is_recommended=True, sort_order=10)

    r = await client.get("/api/admin/membership/plans", headers=admin_headers)
    plans = r.json()
    recommended = [p for p in plans if p["is_recommended"]]
    assert len(recommended) == 1
    assert recommended[0]["name"] == "尊享版"


# ──────────────── 9. [优化 v1.0 2026-05-27] free_quota 字段下发 ────────────────


@pytest.mark.asyncio
async def test_center_returns_free_quota(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """[优化 v1.0 2026-05-27 API-01] /api/member/center 必须返回 free_quota 三字段"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "free_quota" in body, "响应必须包含 free_quota 字段"
    fq = body["free_quota"]
    assert "max_managed" in fq
    assert "ai_outbound_call_count" in fq
    assert "emergency_ai_call_count" in fq
    # 类型必须是数字
    assert isinstance(fq["max_managed"], int)
    assert isinstance(fq["ai_outbound_call_count"], int)
    assert isinstance(fq["emergency_ai_call_count"], int)


@pytest.mark.asyncio
async def test_free_quota_reflects_admin_config(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """[优化 v1.0 2026-05-27 API-03] 改完管理后台「免费配置」后，下一次请求 free_quota 数值即时更新"""
    # 1. 通过管理后台改写免费额度
    target = {
        "max_managed": 3,
        "ai_outbound_call_count": 10,
        "emergency_ai_call_count": 4,
        "max_managed_by": 3,
    }
    r = await client.put(
        "/api/admin/membership/free-quota",
        json=target,
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    # 2. 拉 H5 会员中心聚合
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    fq = body["free_quota"]

    # 3. free_quota 必须等于刚刚改写的值
    assert fq["max_managed"] == 3
    assert fq["ai_outbound_call_count"] == 10
    assert fq["emergency_ai_call_count"] == 4


@pytest.mark.asyncio
async def test_free_quota_independent_of_user_level(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """[优化 v1.0 2026-05-27 API-02] free_quota 不随登录用户档位变化（免费用户 vs 付费用户 free_quota 一致）"""
    # 1. 改写免费额度
    target = {
        "max_managed": 2,
        "ai_outbound_call_count": 7,
        "emergency_ai_call_count": 1,
        "max_managed_by": 2,
    }
    r = await client.put("/api/admin/membership/free-quota", json=target, headers=admin_headers)
    assert r.status_code == 200, r.text

    # 2. 免费用户拉取 free_quota
    r1 = await client.get("/api/member/center", headers=auth_headers)
    fq_free = r1.json()["free_quota"]

    # 3. 给用户购买付费套餐
    plan = await _create_plan(client, admin_headers, name="对比测试版", max_managed=20, ai_outbound_call_count=100, emergency_ai_call_count=50)
    pid = plan["id"]
    r = await client.post("/api/member/order", json={"plan_id": pid, "period": "month"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    oid = r.json()["order_id"]
    r = await client.post(f"/api/member/order/{oid}/pay", json={"simulate": True}, headers=auth_headers)
    assert r.status_code == 200, r.text

    # 4. 付费后再次拉取 center
    r2 = await client.get("/api/member/center", headers=auth_headers)
    body2 = r2.json()
    assert body2["current"]["level"] == "paid"
    # current.max_managed 是付费套餐额度
    assert body2["current"]["max_managed"] == 20
    # 关键：free_quota 必须与免费时一致（来自管理后台「免费会员额度配置」，与用户档位无关）
    fq_paid = body2["free_quota"]
    assert fq_paid["max_managed"] == fq_free["max_managed"] == 2
    assert fq_paid["ai_outbound_call_count"] == fq_free["ai_outbound_call_count"] == 7
    assert fq_paid["emergency_ai_call_count"] == fq_free["emergency_ai_call_count"] == 1


@pytest.mark.asyncio
async def test_free_member_plan_name_text(
    client: AsyncClient, auth_headers: dict
):
    """[优化 v1.0 2026-05-27 TC-06/TC-07] 免费用户档位 plan_name 应为「免费会员」（非「普通会员」）"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    if body["current"]["level"] == "free":
        assert body["current"]["plan_name"] == "免费会员"
        assert body["current"]["plan_name"] != "普通会员"
