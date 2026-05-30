"""[PRD-INVITE-FAMILY-CARD-V1 2026-05-30] 邀请家人入口卡片 - 后端数据来源验证测试

本次需求是纯前端视觉/交互改造，零后端 schema 改动。本测试用例只为
验证：邀请家人入口卡片所依赖的数据来源接口仍按 PRD 约定的口径（含本人）
返回字段，且不限档语义保持不变。

PRD §2.3 F4 数据取数清单：
  - planName  : /api/member/center -> current.plan_name
  - quotaMax  : /api/family/member/quota -> quota_max（含本人，原值，-1/9999 表示不限）
  - quotaUsed : /api/family/member/quota -> quota_used（含本人）

业务规则：
  - BR-01：含本人口径
  - BR-02：不限档（-1 / >=9999）永远不进入达上限态（quota_max 透传 -1）
  - BR-05：plan_name / quota_max / quota_used 在 API 响应中始终存在（前端兜底文案不依赖后端字段缺失）
"""

import pytest
from httpx import AsyncClient


# ──────────── helpers ────────────

async def _create_plan(client: AsyncClient, admin_headers: dict, **overrides):
    payload = {
        "name": "邀请卡片测试套餐",
        "description": "PRD-INVITE-FAMILY-CARD-V1 数据来源验证",
        "price_month": 99.0,
        "price_year": 999.0,
        "max_managed": 10,
        "ai_outbound_call_count": 20,
        "emergency_ai_call_count": 10,
        "max_managed_by": 5,
        "discount_rate": None,
        "is_active": True,
        "is_recommended": False,
        "sort_order": 100,
    }
    payload.update(overrides)
    r = await client.post("/api/admin/membership/plans", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# ──────────── 数据来源 1：/api/member/center 提供 plan_name ────────────


@pytest.mark.asyncio
async def test_invite_card_plan_name_from_member_center(
    client: AsyncClient, auth_headers: dict
):
    """[PRD §2.3 F4] 邀请卡片读取的套餐名 = /api/member/center current.plan_name，且非空"""
    res = await client.get("/api/member/center", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    current = body.get("current") or body.get("data", {}).get("current")
    assert current is not None, "/api/member/center 必须返回 current 段"
    plan_name = current.get("plan_name")
    assert isinstance(plan_name, str), f"plan_name 必须为字符串，实际 {type(plan_name).__name__}"
    assert plan_name.strip(), "plan_name 不应为空字符串（前端依赖此字段渲染套餐名）"


# ──────────── 数据来源 2：/api/family/member/quota 提供 quota_max / quota_used（含本人） ────────────


@pytest.mark.asyncio
async def test_invite_card_quota_endpoint_returns_required_fields(
    client: AsyncClient, auth_headers: dict
):
    """[PRD §2.3 F4 / BR-05] /api/family/member/quota 必须始终返回 quota_max + quota_used 字段"""
    r = await client.get("/api/family/member/quota", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "quota_max" in body, "quota_max 字段缺失，前端卡片无法渲染"
    assert "quota_used" in body, "quota_used 字段缺失，前端卡片无法渲染"
    assert isinstance(body["quota_max"], int), "quota_max 必须为整数"
    assert isinstance(body["quota_used"], int), "quota_used 必须为整数"


@pytest.mark.asyncio
async def test_invite_card_quota_used_includes_self(
    client: AsyncClient, auth_headers: dict
):
    """[PRD BR-01 / v1.1] quota_used 含本人，新注册用户至少 = 1（自动创建本人卡）"""
    r = await client.get("/api/family/member/quota", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["quota_used"] >= 1, (
        f"quota_used 必须含本人卡（>=1），实际 {body['quota_used']}。"
        "前端卡片用量行 '已管理 X / 上限 Y' 依赖此口径。"
    )


@pytest.mark.asyncio
async def test_invite_card_quota_max_unlimited_semantic_aligned(
    client: AsyncClient, auth_headers: dict
):
    """[PRD §2.3 F4 / BR-02] /api/family/member/quota.quota_max 与 /api/member/center.current.max_managed
    在「不限档」语义上保持一致：要么都为 -1（不限），要么都为有限值（>=0）。
    具体数值可能因 schema_sync 迁移和 free_member_quota 配置而不同（这正是前端卡片
    quotaMax 兜底优先取 quota 接口、再取 current 的原因），但语义类必须一致。
    """
    r1 = await client.get("/api/family/member/quota", headers=auth_headers)
    r2 = await client.get("/api/member/center", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    quota_max = r1.json()["quota_max"]
    center_current = r2.json().get("current") or r2.json().get("data", {}).get("current")
    center_max = center_current["max_managed"]

    def is_unlimited(v: int) -> bool:
        return v == -1 or v >= 9999

    assert is_unlimited(quota_max) == is_unlimited(center_max), (
        f"quota.quota_max({quota_max}) 与 current.max_managed({center_max}) 必须在不限档语义上一致："
        "都为不限或都为有限"
    )
    # 两个值都应为整数，且对前端卡片可用（>=0 或 -1）
    assert isinstance(quota_max, int) and (quota_max >= 0 or quota_max == -1)
    assert isinstance(center_max, int) and (center_max >= 0 or center_max == -1)


# ──────────── BR-02：不限档（-1）永远不进入达上限态 ────────────


@pytest.mark.asyncio
async def test_invite_card_unlimited_plan_quota_max_negative_one(
    client: AsyncClient, admin_headers: dict
):
    """[PRD BR-02] 不限档套餐 max_managed=-1 透传，前端据此判定不限档永不达上限"""
    plan = await _create_plan(
        client, admin_headers, name="邀请卡片不限档", max_managed=-1
    )
    assert plan["max_managed"] == -1, "不限档套餐 max_managed=-1 透传"

    # admin 列表也透传
    rl = await client.get("/api/admin/membership/plans", headers=admin_headers)
    target = next((p for p in rl.json() if p["id"] == plan["id"]), None)
    assert target is not None
    assert target["max_managed"] == -1


# ──────────── BR-05：兜底——免费会员场景下 plan_name 仍存在 ────────────


@pytest.mark.asyncio
async def test_invite_card_free_user_plan_name_fallback(
    client: AsyncClient, auth_headers: dict
):
    """[PRD BR-05] 免费会员：current.plan_name 应为 '免费会员'（非空），
    前端卡片可直接读取并展示"""
    res = await client.get("/api/member/center", headers=auth_headers)
    body = res.json()
    current = body.get("current") or body.get("data", {}).get("current")
    # auth_headers 默认是免费会员
    if current.get("level") == "free":
        assert current.get("plan_name") == "免费会员", (
            f"免费会员的 plan_name 应为 '免费会员'，实际 {current.get('plan_name')!r}"
        )
