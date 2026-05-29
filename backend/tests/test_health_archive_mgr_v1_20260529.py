"""[PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 健康档案管理优化（命名升级）

测试覆盖：
1. /api/member/center 响应中 benefits_cards 的 max_managed 卡片：
   - label 从「守护人数量」改为「可管理健康档案」
   - unit 从「人」改为「份（含本人）」
   - value 字段保留 max_managed 原始值（仅家人/守护对象计数，不含本人）
   - 其他卡片（AI 外呼 / 紧急 AI 呼叫 / 占位卡）不受影响
2. /api/member/plans 字段不变：max_managed 字段名保留（接口零变更）
3. 数据库字段名零变更：membership_plans.max_managed 与 free_member_quota.max_managed 保留

PRD 决策（§7.4）：
> 数据库不动（max_managed 字段保留）；接口不动（字段名保留）；仅前端文案 + 后端注释改
"""

import pytest
from httpx import AsyncClient


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


# ──────────────── TC-ARCH-01: benefits_cards 文案对齐 ────────────────


@pytest.mark.asyncio
async def test_benefits_cards_max_managed_label_updated(
    client: AsyncClient, auth_headers: dict
):
    """免费会员视图：benefits_cards 中 max_managed 卡片的 label/unit 已对齐"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    cards = body["benefits_cards"]
    assert len(cards) == 4, "benefits_cards 仍为 4 项（3 实卡 + 1 占位）"

    max_managed_card = next((c for c in cards if c["key"] == "max_managed"), None)
    assert max_managed_card is not None, "benefits_cards 中必须包含 max_managed 卡片"

    # [PRD-HEALTH-ARCHIVE-MGR-V1 §3.1] label 升级
    assert max_managed_card["label"] == "可管理健康档案", \
        f"max_managed 卡片 label 必须为「可管理健康档案」，实际为 {max_managed_card['label']!r}"
    # [PRD-HEALTH-ARCHIVE-MGR-V1 §3.1] unit 升级
    assert max_managed_card["unit"] == "份（含本人）", \
        f"max_managed 卡片 unit 必须为「份（含本人）」，实际为 {max_managed_card['unit']!r}"


@pytest.mark.asyncio
async def test_benefits_cards_other_cards_intact(
    client: AsyncClient, auth_headers: dict
):
    """其他卡片（AI 外呼 / 紧急 AI 呼叫 / 占位卡）不受本次改名影响"""
    r = await client.get("/api/member/center", headers=auth_headers)
    body = r.json()
    cards = body["benefits_cards"]

    ai_card = next((c for c in cards if c["key"] == "ai_outbound_call_count"), None)
    assert ai_card is not None
    assert ai_card["label"] == "AI 外呼提醒"
    assert ai_card["unit"] == "次/月"

    em_card = next((c for c in cards if c["key"] == "emergency_ai_call_count"), None)
    assert em_card is not None
    assert em_card["label"] == "紧急 AI 呼叫"
    assert em_card["unit"] == "次/月"

    ph_card = next((c for c in cards if c["key"] == "placeholder"), None)
    assert ph_card is not None
    assert ph_card["label"] == "更多权益"
    assert ph_card["unit"] == "敬请期待"


# ──────────────── TC-ARCH-02: max_managed 字段名零变更（接口契约） ────────────────


@pytest.mark.asyncio
async def test_max_managed_field_name_preserved_in_plan_create(
    client: AsyncClient, admin_headers: dict
):
    """后台新建套餐：接口仍接受 max_managed 字段名（PRD §7.4 零迁移成本）"""
    plan = await _create_plan(client, admin_headers, name="档案管理版", max_managed=7)
    assert plan["max_managed"] == 7, \
        "接口返回必须仍包含 max_managed 字段（字段名保留，仅前端文案改）"
    assert "max_managed" in plan


@pytest.mark.asyncio
async def test_max_managed_field_name_preserved_in_plans_list(
    client: AsyncClient, admin_headers: dict
):
    """/api/member/plans 列表接口字段名保留"""
    await _create_plan(client, admin_headers, name="档案管理版 2", max_managed=8)
    r = await client.get("/api/member/plans")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    plan = data[0]
    assert "max_managed" in plan, "接口字段名 max_managed 必须保留"


@pytest.mark.asyncio
async def test_max_managed_value_unchanged_in_center(
    client: AsyncClient, auth_headers: dict
):
    """/api/member/center 中 max_managed 卡片的 value 仍是原始 max_managed 值，
    不在后端做 +1 含本人转换（含本人转换由前端展示层处理）。"""
    r = await client.get("/api/member/center", headers=auth_headers)
    body = r.json()
    current_max_managed = body["current"]["max_managed"]

    max_managed_card = next(
        (c for c in body["benefits_cards"] if c["key"] == "max_managed"), None
    )
    assert max_managed_card is not None
    # PRD §7.4：value 保留原始 max_managed 含义（不含本人），用户端展示时 +1
    assert max_managed_card["value"] == current_max_managed, \
        f"benefits_cards.max_managed.value 应等于 current.max_managed（保留原始语义），" \
        f"value={max_managed_card['value']} vs current={current_max_managed}"


# ──────────────── TC-ARCH-03: 不限场景 ────────────────


@pytest.mark.asyncio
async def test_max_managed_unlimited_value_preserved(
    client: AsyncClient, admin_headers: dict
):
    """max_managed = -1（不限）场景：接口仍正确返回 -1（前端展示「不限」）"""
    plan = await _create_plan(
        client, admin_headers, name="不限档", max_managed=-1
    )
    assert plan["max_managed"] == -1

    r = await client.get("/api/member/plans")
    plans = r.json()
    unlimited = [p for p in plans if p["max_managed"] == -1]
    assert len(unlimited) >= 1, "不限档套餐应在 /api/member/plans 中按原值返回 -1"
