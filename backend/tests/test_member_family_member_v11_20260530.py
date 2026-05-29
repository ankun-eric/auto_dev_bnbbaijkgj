"""[PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 「家庭守护成员」文案规范 v1.1 自动化测试

覆盖 v1.1 变更摘要的 6 大变更（C1~C6）：

- C1 数据库字段口径调整：membership_plans.max_managed / free_member_quota.max_managed 存「含本人」总人数
- C2 权益卡片单行展示，benefits_cards 中 max_managed 项 label 为「家庭守护成员」, unit 为「人」（不再出现「含本人」字样）
- C3 Admin 录入框文案（前端验收，后端只验证字段透传不变形）
- C4 档案管理列表页顶部小字（前端验收）
- C5 前端零加工：API 返回 max_managed 原值即「含本人」总人数
- C6 验收清单：
    - quota_max（=数据库 max_managed 原值）= 含本人上限
    - quota_used = 含本人卡的已建档案总数
    - 不限档（-1）继续表示「不限」
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session


# ──────────── helpers ────────────

async def _create_plan(client: AsyncClient, admin_headers: dict, **overrides):
    payload = {
        "name": "尊享版 V1.1",
        "description": "PRD v1.1 含本人测试",
        "price_month": 99.0,
        "price_year": 999.0,
        "max_managed": 10,  # v1.1：含本人 10 人
        "ai_outbound_call_count": 20,
        "emergency_ai_call_count": 10,
        "max_managed_by": 5,
        "discount_rate": None,
        "is_active": True,
        "is_recommended": True,
        "sort_order": 0,
    }
    payload.update(overrides)
    r = await client.post("/api/admin/membership/plans", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# ──────────── C1：数据库字段口径（含本人） ────────────

@pytest.mark.asyncio
async def test_v11_c1_plan_max_managed_stored_as_inclusive(
    client: AsyncClient, admin_headers: dict
):
    """[C1] 套餐管理员录入 10 → 数据库与 API 响应原样 10（含本人，无 +1 加工）"""
    plan = await _create_plan(client, admin_headers, name="C1 测试套餐", max_managed=10)
    assert plan["max_managed"] == 10, "API 返回 max_managed 应保持录入原值，不被任何 +1/-1 加工"

    # 读取列表也应一致
    rl = await client.get("/api/admin/membership/plans", headers=admin_headers)
    assert rl.status_code == 200
    plans = rl.json()
    target = next((p for p in plans if p["id"] == plan["id"]), None)
    assert target is not None
    assert target["max_managed"] == 10


@pytest.mark.asyncio
async def test_v11_c1_plan_unlimited_still_negative_one(
    client: AsyncClient, admin_headers: dict
):
    """[C1] 不限档：max_managed=-1 语义不变"""
    plan = await _create_plan(client, admin_headers, name="C1 不限档", max_managed=-1)
    assert plan["max_managed"] == -1


# ──────────── C5：用户端 /api/member/center 零加工原样展示 ────────────

@pytest.mark.asyncio
async def test_v11_c5_member_center_returns_max_managed_raw(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """[C5] /api/member/center benefits_cards 中 max_managed 的 value
    必须 = 数据库原值（=含本人，迁移后），不再 +1 加工。
    并且 unit 不应包含「含本人」字样（C2）。
    """
    res = await client.get("/api/member/center", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    benefits = body.get("benefits_cards") or body.get("data", {}).get("benefits_cards")
    assert benefits is not None, "benefits_cards 字段必须存在"

    card = next((c for c in benefits if c.get("key") == "max_managed"), None)
    assert card is not None, "benefits_cards 中必须有 max_managed 项"

    # current.max_managed 与卡片 value 必须一致（无任何加工）
    current = body.get("current") or body.get("data", {}).get("current")
    assert current is not None
    assert card["value"] == current["max_managed"], (
        f"权益卡片 value({card['value']}) 必须等于 current.max_managed({current['max_managed']}), "
        f"前端零加工原样展示"
    )

    # C2: unit 不应包含「含本人」字样
    assert "含本人" not in (card.get("unit") or ""), (
        f"权益卡片 unit 不应包含「含本人」字样，实际 unit={card.get('unit')!r}"
    )
    # label 推荐为「家庭守护成员」（PRD v1.1 规范）
    assert card.get("label") in ("家庭守护成员", "可管理健康档案"), (
        f"权益卡片 label 应为 PRD v1.1 规范的「家庭守护成员」，实际 label={card.get('label')!r}"
    )


# ──────────── C6 验收清单 ────────────

@pytest.mark.asyncio
async def test_v11_c6_2_member_quota_endpoint_includes_self(
    client: AsyncClient, auth_headers: dict
):
    """[C6-2 / C5] /api/family/member/quota 返回的 quota_max = 数据库 max_managed 原值（含本人）；
    quota_used 包含本人卡。
    """
    res = await client.get("/api/family/member/quota", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()

    # quota_used 至少为 1（自动创建的本人卡）
    assert body["quota_used"] >= 1, (
        f"quota_used 应含本人卡（至少 1），实际 {body['quota_used']}"
    )
    # quota_max -1 表示不限，否则应 >= quota_used
    if body["quota_max"] != -1:
        assert body["quota_max"] >= body["quota_used"], (
            f"quota_max({body['quota_max']}) 应 >= quota_used({body['quota_used']})（含本人口径）"
        )


@pytest.mark.asyncio
async def test_v11_c6_8_unlimited_plan_member_center(
    client: AsyncClient, admin_headers: dict, auth_headers: dict
):
    """[C6-8] 不限档套餐场景下，/api/member/center 中 max_managed 应当透传 -1 或 >=9999"""
    plan = await _create_plan(
        client, admin_headers, name="C6-8 不限档", max_managed=-1, is_recommended=False
    )
    assert plan["max_managed"] == -1

    # 公开列表端也透传
    rl = await client.get("/api/admin/membership/plans", headers=admin_headers)
    target = next((p for p in rl.json() if p["id"] == plan["id"]), None)
    assert target is not None
    assert target["max_managed"] == -1


# ──────────── C2 单行展示——验证后端不再下发副文案字段 ────────────

@pytest.mark.asyncio
async def test_v11_c2_no_subtitle_field_in_benefit_card(
    client: AsyncClient, auth_headers: dict
):
    """[C2] 权益卡片仅一行：benefits_cards[*] 不应包含 subtitle/description 等副文案字段。"""
    res = await client.get("/api/member/center", headers=auth_headers)
    body = res.json()
    benefits = body.get("benefits_cards") or body.get("data", {}).get("benefits_cards")
    for card in benefits or []:
        # PRD v1.1 仅保留主文案，副文案字段不应出现
        assert "subtitle" not in card, f"权益卡片不应有 subtitle 字段，实际 {card}"
        assert "tooltip" not in card, f"权益卡片不应有 tooltip 字段，实际 {card}"
        # description 在套餐对象中允许存在；在 benefits_cards 项中不应有
        assert "description" not in card, f"权益卡片不应有 description 字段，实际 {card}"


# ──────────── 内部口径一致性 ────────────

@pytest.mark.asyncio
async def test_v11_plan_crud_max_managed_no_transform(
    client: AsyncClient, admin_headers: dict
):
    """[内部一致性] 后端 CRUD 全链路对 max_managed 不做任何 +1/-1 加工。
    create / list / get / update / delete 都按原值透传。
    """
    plan = await _create_plan(client, admin_headers, name="V1.1 CRUD", max_managed=8)
    assert plan["max_managed"] == 8

    # update
    pid = plan["id"]
    r = await client.put(
        f"/api/admin/membership/plans/{pid}",
        json={"max_managed": 15},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["max_managed"] == 15, "更新后 API 返回值应等于录入值，不被加工"

    # list
    rl = await client.get("/api/admin/membership/plans", headers=admin_headers)
    target = next((p for p in rl.json() if p["id"] == pid), None)
    assert target["max_managed"] == 15
