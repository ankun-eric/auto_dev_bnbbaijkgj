"""[PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 新增家庭成员优化（最终版）契约测试

需求要点：
- 名额满没满 / 上限是几，全部从 GET /api/family/member/quota 拿，前端绝不写死
- 接口必须稳定返回 quota_max / quota_used / quota_remaining 三个字段
- max=-1 表示不限；满额时 quota_remaining<=0

本测试覆盖：
1) GET /api/family/member/quota 返回结构契约（含必要字段、字段类型）
2) quota_remaining 与 quota_max - quota_used 关系自洽（限额非 -1 时）
3) 与其他配额接口（/api/member/quota-usage）数字对齐（已有测试覆盖，本处仅做最小冒烟）
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_family_member_quota_contract(
    client: AsyncClient, auth_headers: dict
):
    """[PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 配额接口必须稳定返回前端依赖的字段。

    前端三端「名额已满」弹框 / 配额检查 完全依赖此接口的返回结构，
    任何字段缺失或类型变化都会导致弹框文案错误或写死回退。
    """
    r = await client.get("/api/family/member/quota", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # 必填字段
    assert "quota_max" in data, "缺少 quota_max 字段（前端满额弹框文案直接用此值）"
    assert "quota_used" in data, "缺少 quota_used 字段"
    assert "quota_remaining" in data, "缺少 quota_remaining 字段（前端用此判断是否满额）"
    # 字段类型
    assert isinstance(data["quota_max"], int), "quota_max 必须是整数"
    assert isinstance(data["quota_used"], int), "quota_used 必须是整数"
    assert isinstance(data["quota_remaining"], int), "quota_remaining 必须是整数"


@pytest.mark.asyncio
async def test_family_member_quota_remaining_consistency(
    client: AsyncClient, auth_headers: dict
):
    """quota_remaining 与 quota_max - quota_used 自洽（quota_max != -1 时）；
    quota_max == -1 时 quota_remaining 应为正大值（不限）。"""
    r = await client.get("/api/family/member/quota", headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    qm = d["quota_max"]
    qu = d["quota_used"]
    qr = d["quota_remaining"]
    if qm == -1:
        # 不限
        assert qr >= 0, "quota_max=-1（不限）时 quota_remaining 至少 >= 0"
    else:
        assert qr == max(0, qm - qu), (
            f"quota_remaining 计算不一致：max={qm}, used={qu}, "
            f"expected_remaining={max(0, qm - qu)}, got={qr}"
        )


@pytest.mark.asyncio
async def test_family_member_quota_smoke_align_with_member_quota_usage(
    client: AsyncClient, auth_headers: dict
):
    """冒烟：family/member/quota.quota_used 应与 member/quota-usage.max_managed_used 一致
    （已被 test_member_count_consistency 覆盖，本处仅作最小回归保护）。"""
    r1 = await client.get("/api/family/member/quota", headers=auth_headers)
    r2 = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r1.status_code == 200
    if r2.status_code != 200:
        # 该接口在某些精简部署下可能未启用，本测试不强制
        return
    d1 = r1.json()
    d2 = r2.json()
    if "max_managed_used" in d2:
        assert d1["quota_used"] == d2["max_managed_used"], (
            f"两口径数字不一致：quota_used={d1['quota_used']} vs "
            f"max_managed_used={d2['max_managed_used']}"
        )
