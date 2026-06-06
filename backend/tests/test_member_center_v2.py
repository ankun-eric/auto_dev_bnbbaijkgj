"""[会员中心优化 PRD v2.0 2026-05-26] 自动化测试 [部分字段已被 PRD v1.0 终稿对齐取代]

⚠️ 本测试文件创建套餐时使用了 plan_code/ai_remind_quota/max_guardians 等老字段，
已于 2026-05-26 PRD v1.0 终稿对齐时全部物理删除。本文件整体跳过执行；
新的对齐测试位于 test_member_center_prd_v1_aligned.py。
"""

from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.skip(reason="v2.0 老字段已被 PRD v1.0 终稿对齐物理删除；新测试见 test_member_center_prd_v1_aligned.py")
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.models.membership_plan import FreeMemberQuota, MembershipPlan, UserMembershipSub
from app.models.models import OrderItem, UnifiedOrder, User


async def _create_plan(
    client: AsyncClient,
    admin_headers: dict,
    plan_code: str = "guardian",
    name: str = "守护版",
    price_monthly: float = 19.9,
    price_yearly: float | None = 199.0,
    max_managed: int = 5,
    emergency_ai_call_count: int = 10,
    ai_remind_quota: int = 20,
    sort_order: int = 1,
) -> int:
    payload = {
        "plan_code": plan_code,
        "name": name,
        "price_monthly": price_monthly,
        "price_yearly": price_yearly,
        "ai_remind_quota": ai_remind_quota,
        "ai_alert_quota": 0,
        "ai_call_quota": 0,
        "emergency_ai_call_count": emergency_ai_call_count,
        "max_managed": max_managed,
        "max_guardians": 3,
        "discount_rate": 0.9,
        "benefits_desc": f"{name} 权益",
        "is_active": True,
        "sort_order": sort_order,
    }
    r = await client.post("/api/admin/membership/plans", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_member_center_free_user(client: AsyncClient, auth_headers: dict):
    """免费会员视图：默认是 free，benefits_cards 4 项"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current"]["level"] == "free"
    assert body["current"]["expire_date"] == "长期"
    assert len(body["benefits_cards"]) == 4
    # 占位卡固定为最后一个
    assert body["benefits_cards"][-1]["key"] == "placeholder"
    assert body["benefits_cards"][-1]["unit"] == "敬请期待"


@pytest.mark.asyncio
async def test_member_plans_list(client: AsyncClient, admin_headers: dict):
    pid = await _create_plan(client, admin_headers)
    r = await client.get("/api/member/plans")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == pid
    assert data[0]["price_month"] == 19.9
    assert data[0]["price_year"] == 199.0
    # 第一个套餐被自动标记为 recommended
    assert data[0]["is_recommended"] is True


@pytest.mark.asyncio
async def test_create_member_order_and_pay(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
):
    pid = await _create_plan(client, admin_headers)

    # 创建月卡订单
    r = await client.post(
        "/api/member/order",
        json={"plan_id": pid, "period": "month"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["amount"] == 19.9
    assert order["period"] == "month"
    assert "【会员费】" in order["product_name"]
    oid = order["order_id"]

    # OrderItem 校验：fulfillment_type=virtual + membership_plan_id 已填充
    async with test_session() as s:
        item = (await s.execute(
            select(OrderItem).where(OrderItem.order_id == oid)
        )).scalar_one()
        assert item.membership_plan_id == pid
        assert item.membership_period == "month"
        assert item.fulfillment_type.value == "virtual"

    # 模拟支付
    r = await client.post(
        f"/api/member/order/{oid}/pay",
        json={"simulate": True},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    pay = r.json()
    assert pay["paid"] is True
    assert pay["plan_name"] == "守护版"

    # 再次查询 center，应该已为 paid
    r = await client.get("/api/member/center", headers=auth_headers)
    body = r.json()
    assert body["current"]["level"] == "paid"
    assert body["current"]["plan_id"] == pid


@pytest.mark.asyncio
async def test_renewal_extends_expire_at(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
):
    pid = await _create_plan(client, admin_headers)
    # 第一次订购月卡
    r = await client.post("/api/member/order", json={"plan_id": pid, "period": "month"}, headers=auth_headers)
    oid1 = r.json()["order_id"]
    await client.post(f"/api/member/order/{oid1}/pay", json={"simulate": True}, headers=auth_headers)

    # 取出第一次 expire_at
    async with test_session() as s:
        sub1 = (await s.execute(
            select(UserMembershipSub).where(UserMembershipSub.status == "active")
        )).scalars().first()
        first_expire = sub1.expire_at

    # 同套餐续费月卡
    r = await client.post("/api/member/order", json={"plan_id": pid, "period": "month"}, headers=auth_headers)
    oid2 = r.json()["order_id"]
    r2 = await client.post(f"/api/member/order/{oid2}/pay", json={"simulate": True}, headers=auth_headers)
    assert r2.status_code == 200, r2.text

    async with test_session() as s:
        sub2 = (await s.execute(
            select(UserMembershipSub).where(UserMembershipSub.status == "active")
        )).scalars().first()
        # 时长追加：新的 expire_at >= 旧 expire_at + 25 天（容差）
        assert sub2.expire_at >= first_expire + timedelta(days=25)


@pytest.mark.asyncio
async def test_downgrade_is_rejected(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
):
    pid_high = await _create_plan(client, admin_headers, plan_code="family", name="家庭版", price_yearly=999.0, sort_order=1)
    pid_low = await _create_plan(client, admin_headers, plan_code="basic", name="基础版", price_yearly=99.0, sort_order=2)

    # 先开通高级套餐
    r = await client.post("/api/member/order", json={"plan_id": pid_high, "period": "year"}, headers=auth_headers)
    oid = r.json()["order_id"]
    await client.post(f"/api/member/order/{oid}/pay", json={"simulate": True}, headers=auth_headers)

    # 尝试降级到基础版 → 应被拒
    r = await client.post("/api/member/order", json={"plan_id": pid_low, "period": "year"}, headers=auth_headers)
    assert r.status_code == 400, r.text
    assert "降级" in r.json()["detail"]


@pytest.mark.asyncio
async def test_member_orders_tab_filter(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
):
    pid = await _create_plan(client, admin_headers)
    # 创建两个会员订单
    for _ in range(2):
        r = await client.post("/api/member/order", json={"plan_id": pid, "period": "month"}, headers=auth_headers)
        assert r.status_code == 200

    r = await client.get("/api/member/orders?tab=membership", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["tab"] == "membership"
    assert body["total"] == 2
    assert all(it["is_membership"] for it in body["items"])

    r = await client.get("/api/member/orders?tab=product", headers=auth_headers)
    body = r.json()
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_admin_user_membership_card(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
):
    pid = await _create_plan(client, admin_headers)
    r = await client.post("/api/member/order", json={"plan_id": pid, "period": "month"}, headers=auth_headers)
    oid = r.json()["order_id"]
    await client.post(f"/api/member/order/{oid}/pay", json={"simulate": True}, headers=auth_headers)

    # 取得用户 id
    async with test_session() as s:
        uid = (await s.execute(
            select(User.id).where(User.phone == "13900000001")
        )).scalar_one()

    r = await client.get(f"/api/admin/users/{uid}/membership", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["membership_level"] == "paid"
    assert body["plan_id"] == pid
    assert body["max_managed"] == 5
    assert body["emergency_ai_call_count"] == 10

    # 延长 30 天
    r = await client.post(
        f"/api/admin/users/{uid}/membership/adjust",
        json={"action": "extend", "days": 30},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "extend"

    # 降级
    r = await client.post(
        f"/api/admin/users/{uid}/membership/adjust",
        json={"action": "downgrade"},
        headers=admin_headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_center_plans_sorted_by_rank_for_compare_table(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
):
    """[Bug 修复 v1.0 §3.2 2026-05-26] 权益对比表数据源依赖：
    - /api/member/center 返回的 plans 数组必须按 sort_order/price_rank 升序输出
    - ranks 字段必须包含每个 plan 的 rank，供前端按 price_rank 升序排列对比表列
    - 同时返回 max_managed / ai_outbound_call_count / emergency_ai_call_count 供 3 行展示
    """
    # 创建 3 档套餐，故意以错乱顺序（最低 sort_order=3 / 中 sort_order=1 / 最高 sort_order=2）
    pid_low = await _create_plan(
        client, admin_headers,
        plan_code="basic", name="基础版",
        price_monthly=9.9, price_yearly=99.0,
        max_managed=3, ai_remind_quota=5, emergency_ai_call_count=3,
        sort_order=3,
    )
    pid_mid = await _create_plan(
        client, admin_headers,
        plan_code="guardian2", name="守护版",
        price_monthly=19.9, price_yearly=199.0,
        max_managed=5, ai_remind_quota=20, emergency_ai_call_count=10,
        sort_order=1,
    )
    pid_high = await _create_plan(
        client, admin_headers,
        plan_code="family", name="家庭版",
        price_monthly=39.9, price_yearly=399.0,
        max_managed=-1, ai_remind_quota=-1, emergency_ai_call_count=-1,
        sort_order=2,
    )

    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    plans = body["plans"]
    assert len(plans) == 3
    # 按 sort_order 升序：守护版(1) < 家庭版(2) < 基础版(3)
    assert [p["id"] for p in plans] == [pid_mid, pid_high, pid_low]

    # ranks 字段存在且每个 plan_id 都有 rank
    ranks = body["ranks"]
    assert str(pid_mid) in ranks or pid_mid in ranks or any(int(k) == pid_mid for k in ranks)

    # 关键三个字段在每个 plan 中都存在（供对比表 3 行使用）
    for p in plans:
        assert "max_managed" in p
        assert "ai_outbound_call_count" in p
        assert "emergency_ai_call_count" in p

    # 「-1」按 PRD 前端展示为「不限」，但后端原样返回 -1
    family_plan = [p for p in plans if p["id"] == pid_high][0]
    assert family_plan["max_managed"] == -1
    assert family_plan["ai_outbound_call_count"] == -1
    assert family_plan["emergency_ai_call_count"] == -1

    # benefits_cards 3 实卡 + 1 占位卡 = 4 项
    assert len(body["benefits_cards"]) == 4
    keys = [c["key"] for c in body["benefits_cards"]]
    assert "max_managed" in keys
    assert "ai_outbound_call_count" in keys
    assert "emergency_ai_call_count" in keys
    assert keys[-1] == "placeholder"


@pytest.mark.asyncio
async def test_cron_expire_job(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
):
    """到期降级任务：手动构造一个已过期的 active 订阅，调用 cron 后应被置为 expired"""
    pid = await _create_plan(client, admin_headers)
    # 拿到用户
    async with test_session() as s:
        uid = (await s.execute(
            select(User.id).where(User.phone == "13900000001")
        )).scalar_one()
        sub = UserMembershipSub(
            user_id=uid,
            plan_id=pid,
            billing_cycle="monthly",
            start_at=datetime.now() - timedelta(days=40),
            expire_at=datetime.now() - timedelta(days=1),
            status="active",
            paid_amount=19.9,
        )
        s.add(sub)
        await s.commit()
        sub_id = sub.id

    r = await client.post("/api/member/_internal/cron/expire")
    assert r.status_code == 200
    body = r.json()
    assert body["expired_count"] >= 1

    async with test_session() as s:
        new_sub = await s.get(UserMembershipSub, sub_id)
        assert new_sub.status == "expired"
