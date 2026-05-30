"""[PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 会员中心『付费态蓝紫主题』后端数据层验证

本次 PRD 主要是 H5 视觉/交互改造。后端只新增一个轻量只读接口 /api/member/quota-usage
返回当前用户本月已用配额（AI 外呼/紧急 AI 呼叫/守护他人已用人数）。

本测试覆盖：
1) /api/member/quota-usage 接口对未鉴权请求 401
2) 已鉴权请求返回 200 且字段齐全
3) ai_outbound_call_used / emergency_ai_call_used / max_managed_used 类型为 int 且 >=0
4) period_month 为 YYYY-MM 格式
5) /api/member/center 仍按 PRD 约定的口径返回必需字段（兼容性）
"""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_quota_usage_requires_auth(client: AsyncClient):
    """[PRD §6 权限] /api/member/quota-usage 必须登录才能访问"""
    r = await client.get("/api/member/quota-usage")
    # 不同部署可能 401 / 403，统一接受 4xx
    assert 400 <= r.status_code < 500, f"未登录应返回 4xx，实际 {r.status_code}"


@pytest.mark.asyncio
async def test_quota_usage_returns_required_fields(client: AsyncClient, auth_headers: dict):
    """[PRD-MEMBER-PURPLE-THEME-V1 §F3] /api/member/quota-usage 字段齐全且类型正确"""
    r = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("ai_outbound_call_used", "emergency_ai_call_used", "max_managed_used", "period_month"):
        assert key in body, f"字段 {key} 缺失"
    assert isinstance(body["ai_outbound_call_used"], int)
    assert isinstance(body["emergency_ai_call_used"], int)
    assert isinstance(body["max_managed_used"], int)
    assert body["ai_outbound_call_used"] >= 0
    assert body["emergency_ai_call_used"] >= 0
    assert body["max_managed_used"] >= 0


@pytest.mark.asyncio
async def test_quota_usage_period_month_format(client: AsyncClient, auth_headers: dict):
    """[PRD §F3] period_month 必须是 YYYY-MM 格式"""
    r = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert re.match(r"^\d{4}-\d{2}$", body["period_month"]), f"period_month 格式不符: {body['period_month']}"


@pytest.mark.asyncio
async def test_quota_usage_is_idempotent(client: AsyncClient, auth_headers: dict):
    """[PRD §F3] 多次调用结果一致（只读接口幂等）"""
    r1 = await client.get("/api/member/quota-usage", headers=auth_headers)
    r2 = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["period_month"] == r2.json()["period_month"]


@pytest.mark.asyncio
async def test_member_center_provides_quota_totals_for_purple_card(
    client: AsyncClient, auth_headers: dict
):
    """[PRD §F3] 蓝紫主题『本月配额』卡的"总额"由 /api/member/center 提供

    必须保证 current 段含 ai_outbound_call_count / emergency_ai_call_count / max_managed
    字段，且为整数（-1/9999 表示不限）。
    """
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    current = body.get("current") or body.get("data", {}).get("current")
    assert current is not None
    for key in ("ai_outbound_call_count", "emergency_ai_call_count", "max_managed"):
        assert key in current, f"current.{key} 缺失"
        assert isinstance(current[key], int), f"current.{key} 必须是整数"


@pytest.mark.asyncio
async def test_member_center_level_field_is_free_or_paid(
    client: AsyncClient, auth_headers: dict
):
    """[PRD §1.1] level 字段决定主题切换（free → 浅灰 / paid → 蓝紫）"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    current = body.get("current") or body.get("data", {}).get("current")
    assert current is not None
    assert current["level"] in ("free", "paid"), f"level 仅允许 free/paid，实际 {current['level']}"


@pytest.mark.asyncio
async def test_member_center_days_left_and_expiring_soon_fields_present(
    client: AsyncClient, auth_headers: dict
):
    """[PRD §F6] 即将到期判定依赖 days_left + expiring_soon 字段"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    current = body.get("current") or body.get("data", {}).get("current")
    assert "days_left" in current
    assert "expiring_soon" in current
    # days_left 可为 null（免费用户）或 int
    assert current["days_left"] is None or isinstance(current["days_left"], int)
    assert isinstance(current["expiring_soon"], bool)


@pytest.mark.asyncio
async def test_member_center_plan_name_present(client: AsyncClient, auth_headers: dict):
    """[PRD §5.5] 等级徽章配色依据 plan_name 文本判定（尊享/健康/普通）"""
    r = await client.get("/api/member/center", headers=auth_headers)
    body = r.json()
    current = body.get("current") or body.get("data", {}).get("current")
    plan_name = current["plan_name"]
    assert isinstance(plan_name, str)
    assert plan_name.strip()
