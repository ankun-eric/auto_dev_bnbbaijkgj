"""[PRD-MEMBER-CENTER-OPTIM-V1 2026-05-31] 会员中心页面优化（R1+R2+R3）后端验收

本次 PRD 主要是 H5 视觉/交互改造（三独立卡片 + 权益对比压缩 + 全局命名统一）。
后端层面：
- R1 三独立卡片仍依赖既有 /api/member/quota-usage（已用量）与 /api/member/center.current（总额）
- R2 权益对比仍依赖既有 /api/member/center.plans 与 free_quota 数据源
- R3 全局命名统一仅前端文案替换，后端接口字段名严格不动（PRD §3.11）

本测试覆盖：
1) /api/member/quota-usage 仍返回 R1 三独立卡片所需的三项已用量字段
2) /api/member/center.current 仍返回 R1 三独立卡片所需的三项总额字段
3) /api/member/center.plans 字段齐全，可供 R2 权益对比表渲染
4) /api/member/center.free_quota 字段齐全（免费会员列数据源）
5) R3 后端字段名严格不动：仍是 max_managed / ai_outbound_call_count / emergency_ai_call_count
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_r1_quota_usage_provides_three_card_used_values(
    client: AsyncClient, auth_headers: dict
):
    """[PRD R1] 三独立卡片『已用量』来源：/api/member/quota-usage
    必须包含 ai_outbound_call_used / emergency_ai_call_used / max_managed_used
    """
    r = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("ai_outbound_call_used", "emergency_ai_call_used", "max_managed_used"):
        assert key in body, f"R1 三卡片所需『已用』字段 {key} 缺失"
        assert isinstance(body[key], int) and body[key] >= 0


@pytest.mark.asyncio
async def test_r1_member_center_provides_three_card_totals(
    client: AsyncClient, auth_headers: dict
):
    """[PRD R1] 三独立卡片『总额』来源：/api/member/center.current
    必须包含 ai_outbound_call_count / emergency_ai_call_count / max_managed
    """
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    current = body.get("current") or body.get("data", {}).get("current")
    assert current is not None, "/api/member/center 缺 current 段"
    for key in ("ai_outbound_call_count", "emergency_ai_call_count", "max_managed"):
        assert key in current, f"R1 三卡片所需『总额』字段 current.{key} 缺失"
        assert isinstance(current[key], int)


@pytest.mark.asyncio
async def test_r2_compare_table_plans_fields_complete(
    client: AsyncClient, auth_headers: dict
):
    """[PRD R2] 权益对比表数据源：/api/member/center.plans 与 ranks
    每个 plan 必须包含三项权益字段，供前端按 R2 压缩后渲染。
    """
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # 兼容直接返回与 {data:{}} 包裹两种风格
    root = body.get("data") if isinstance(body.get("data"), dict) and "plans" in body.get("data", {}) else body
    plans = root.get("plans") or []
    # ranks 必须存在（升序排列依据）；允许为空字典（无套餐场景）但必须是 dict 类型
    assert "ranks" in root, "ranks 字段缺失，权益对比表无法排序"
    ranks = root["ranks"]
    assert isinstance(ranks, dict)
    # 套餐字段（若有可购套餐则需含必要字段）
    for p in plans:
        for key in (
            "id", "name",
            "max_managed",
            "ai_outbound_call_count",
            "emergency_ai_call_count",
        ):
            assert key in p, f"plan.{key} 缺失"


@pytest.mark.asyncio
async def test_r2_free_quota_present_for_compare_table(
    client: AsyncClient, auth_headers: dict
):
    """[PRD R2] 权益对比『免费会员』列由 free_quota 提供（与登录用户档位无关）
    免费会员额度配置表 free_member_quota → /api/member/center.free_quota
    """
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    free_quota = body.get("free_quota") or body.get("data", {}).get("free_quota")
    # free_quota 可为 None（兜底）或对象；若存在必须含三项
    if free_quota is not None:
        for key in (
            "max_managed",
            "ai_outbound_call_count",
            "emergency_ai_call_count",
        ):
            assert key in free_quota, f"free_quota.{key} 缺失"


@pytest.mark.asyncio
async def test_r3_backend_field_names_unchanged_after_rename(
    client: AsyncClient, auth_headers: dict
):
    """[PRD R3 §3.11] 全局命名统一仅前端文案替换，后端字段名严格不动
    必须严格保留：
    - current.max_managed（不得改为 family_members 等）
    - current.ai_outbound_call_count
    - current.emergency_ai_call_count
    - quota-usage 的 max_managed_used / ai_outbound_call_used / emergency_ai_call_used
    """
    # /api/member/center
    r1 = await client.get("/api/member/center", headers=auth_headers)
    assert r1.status_code == 200
    current = (r1.json().get("current") or r1.json().get("data", {}).get("current"))
    assert "max_managed" in current
    assert "ai_outbound_call_count" in current
    assert "emergency_ai_call_count" in current

    # /api/member/quota-usage
    r2 = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r2.status_code == 200
    body2 = r2.json()
    assert "max_managed_used" in body2
    assert "ai_outbound_call_used" in body2
    assert "emergency_ai_call_used" in body2


@pytest.mark.asyncio
async def test_r1_quota_usage_unauthenticated_blocked(client: AsyncClient):
    """[PRD §6 权限] R1 三独立卡片数据来源接口必须鉴权"""
    r = await client.get("/api/member/quota-usage")
    assert 400 <= r.status_code < 500


@pytest.mark.asyncio
async def test_r2_member_center_unauthenticated_blocked(client: AsyncClient):
    """[PRD §6 权限] R2 权益对比所依赖的会员中心聚合接口必须鉴权"""
    r = await client.get("/api/member/center")
    assert 400 <= r.status_code < 500


@pytest.mark.asyncio
async def test_member_center_level_paid_or_free(client: AsyncClient, auth_headers: dict):
    """会员中心 current.level 仅允许 free/paid，前端依赖此判定主题与三卡片配色"""
    r = await client.get("/api/member/center", headers=auth_headers)
    assert r.status_code == 200
    current = r.json().get("current") or r.json().get("data", {}).get("current")
    assert current["level"] in ("free", "paid")
