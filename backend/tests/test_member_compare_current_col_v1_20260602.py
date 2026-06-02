"""[PRD-MEMBER-COMPARE-CURRENT-COL-V1 2026-06-02] 会员中心『权益对比 当前会员列高亮优化』

本次需求是 H5 前端 BenefitsCompareTable 的纯视觉/交互优化（方案 B「紫金高级」）：
- 「当前」角标内嵌进列头格子（金色系），不再 position:absolute 浮出顶部被卡片边框遮挡
- 当前列整列淡紫底高亮 + 列头顶部紫色横条
- 未开通付费会员（level=free）时全表无角标、无高亮

前端「哪一列是当前列」的判定完全依赖 /api/member/center 返回的 current.level 与 current.plan_id。
因此本（非 UI）自动化测试聚焦于验证后端数据契约稳定、可支撑前端当前列判定：

1) /api/member/center 未登录返回 4xx
2) 已登录返回 200，且 current 含 level / plan_id 字段
3) current.level 取值只能是 free / paid
4) 当 level=free 时 plan_id 必须为 None（前端据此对所有列不高亮）
5) 当 level=paid 时 plan_id 必须是正整数（前端据此精确高亮某一付费列）
6) plans 列表中每个套餐含 id 字段（前端用 current.plan_id === p.id 命中当前列）
7) 接口幂等：多次调用 current.level / current.plan_id 一致
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_member_center_requires_auth(client: AsyncClient):
    """未登录访问会员中心应返回 4xx。"""
    r = await client.get("/api/member/center")
    assert 400 <= r.status_code < 500, f"未登录应返回 4xx，实际 {r.status_code}"


@pytest.mark.asyncio
async def test_member_center_current_has_level_and_plan_id(client: AsyncClient, auth_headers: dict):
    """[当前列判定契约] current 必须含 level 与 plan_id 字段。"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "current" in body, "返回缺少 current 字段"
    current = body["current"]
    assert "level" in current, "current 缺少 level 字段"
    assert "plan_id" in current, "current 缺少 plan_id 字段"


@pytest.mark.asyncio
async def test_member_center_level_value_domain(client: AsyncClient, auth_headers: dict):
    """current.level 取值只能是 free / paid。"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    level = r.json()["current"]["level"]
    assert level in ("free", "paid"), f"level 非法取值: {level}"


@pytest.mark.asyncio
async def test_member_center_plan_id_consistency_with_level(client: AsyncClient, auth_headers: dict):
    """[当前列高亮核心契约]
    - level=free  -> plan_id 必须为 None（前端：所有列不显示「当前」角标与高亮）
    - level=paid  -> plan_id 必须为正整数（前端：据此命中并高亮对应付费列）
    """
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    current = r.json()["current"]
    level = current["level"]
    plan_id = current["plan_id"]
    if level == "free":
        assert plan_id is None, f"免费用户 plan_id 应为 None，实际 {plan_id}"
    else:  # paid
        assert isinstance(plan_id, int) and plan_id > 0, f"付费用户 plan_id 应为正整数，实际 {plan_id}"


@pytest.mark.asyncio
async def test_member_center_plans_have_id(client: AsyncClient, auth_headers: dict):
    """plans 列表中每个套餐必须含 id（前端用 current.plan_id === p.id 命中当前列）。"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    plans = body.get("plans", [])
    assert isinstance(plans, list)
    for p in plans:
        assert "id" in p, f"套餐缺少 id 字段: {p}"
        assert isinstance(p["id"], int), f"套餐 id 应为整数: {p}"


@pytest.mark.asyncio
async def test_member_center_current_idempotent(client: AsyncClient, auth_headers: dict):
    """接口幂等：多次调用 current.level / current.plan_id 一致，保证当前列判定稳定。"""
    r1 = await client.get("/api/member/center", headers=auth_headers)
    r2 = await client.get("/api/member/center", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    c1 = r1.json()["current"]
    c2 = r2.json()["current"]
    assert c1["level"] == c2["level"], "两次调用 level 不一致"
    assert c1["plan_id"] == c2["plan_id"], "两次调用 plan_id 不一致"
