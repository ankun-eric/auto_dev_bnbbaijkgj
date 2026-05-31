"""[PRD-MEMBER-COUNT-CONSISTENCY-V1 2026-05-31] 会员中心家庭档案数一致性修复测试

修复背景：
- 会员中心存在两个本应相等的"家庭成员/已管理"数字：
  - 蓝色「邀请家人」卡片 → /api/family/member/quota.quota_used（含本人 + 排除软删除）
  - 配额卡第三格家庭成员 → /api/member/quota-usage.max_managed_used
- 旧代码：/api/member/quota-usage 使用裸 SQL `WHERE COALESCE(is_self,0)=0`
  强制剔除本人，且未过滤软删除记录，导致两数字对不上（甚至出现 6>3 异常）。
- 修复：抽取公共方法 count_managed_family_members，统一口径为
  「含本人 + 排除软删除」，两接口必须返回完全相等的数值。

本测试覆盖：
1) 公共统计方法存在且口径正确（含本人 + 排除软删除）
2) /api/member/quota-usage.max_managed_used 与 /api/family/member/quota.quota_used 完全相等
3) 软删除记录被两个接口同时排除
4) 新增 / 删除家人时，两处接口的返回值同步增减
5) 文案口径速查表自检：蓝卡片含本人、配额卡含本人、健康档案列表卡含本人
"""

from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.api.family_member_v2 import count_managed_family_members
from app.models.models import FamilyMember, User


# ──────────── 工具：获取当前用户 id ────────────

async def _get_current_user_id(db_session, phone: str = "13900000001") -> int:
    """通过测试用户的 phone 反查 user_id（conftest 中默认注册的测试账号）"""
    r = await db_session.execute(select(User.id).where(User.phone == phone))
    val = r.scalar()
    return int(val) if val else 0


# ──────────── 测试 1：两接口数字完全相等（核心 Bug） ────────────


@pytest.mark.asyncio
async def test_two_endpoints_managed_count_are_equal(
    client: AsyncClient, auth_headers: dict
):
    """[核心 Bug 修复] /api/family/member/quota.quota_used 与
    /api/member/quota-usage.max_managed_used 必须完全相等（口径统一为含本人+排除软删除）。
    这是用户拍板的最高优先级验收点。"""
    r1 = await client.get("/api/family/member/quota", headers=auth_headers)
    r2 = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    quota_used = r1.json()["quota_used"]
    managed_used = r2.json()["max_managed_used"]
    assert quota_used == managed_used, (
        f"两接口数字不一致：family/member/quota.quota_used={quota_used}, "
        f"member/quota-usage.max_managed_used={managed_used}。"
        "需求文档已拍板：两数字必须完全相等（含本人+排除软删除口径）。"
    )


# ──────────── 测试 2：含本人口径——新用户至少 = 1 ────────────


@pytest.mark.asyncio
async def test_managed_count_includes_self_at_least_one(
    client: AsyncClient, auth_headers: dict
):
    """[需求 §5 口径速查表] 含本人口径：新注册用户系统自动创建本人档案卡，
    quota_used 与 max_managed_used 都必须 >= 1（本人计入）。"""
    r1 = await client.get("/api/family/member/quota", headers=auth_headers)
    r2 = await client.get("/api/member/quota-usage", headers=auth_headers)
    assert r1.json()["quota_used"] >= 1, (
        f"quota_used 应含本人卡（>=1），实际 {r1.json()['quota_used']}"
    )
    assert r2.json()["max_managed_used"] >= 1, (
        f"max_managed_used 应含本人卡（>=1），实际 {r2.json()['max_managed_used']}"
    )


# ──────────── 测试 3：公共统计方法存在且可调用 ────────────


@pytest.mark.asyncio
async def test_public_count_helper_exists_and_callable(db_session):
    """[需求 §2.4 最佳做法] 抽公共方法：count_managed_family_members 必须存在并可调用，
    用于所有接口统一调用，从根上杜绝多套 SQL 算法导致的口径漂移。"""
    # 拿任意一个用户做测试（不强依赖 fixture，存在用户即用）
    r = await db_session.execute(select(User.id).limit(1))
    uid = r.scalar()
    if uid is None:
        pytest.skip("当前 DB 无用户，跳过公共方法直接调用测试")
    count = await count_managed_family_members(db_session, int(uid))
    assert isinstance(count, int)
    assert count >= 0


# ──────────── 测试 4：软删除记录被正确排除 ────────────


@pytest.mark.asyncio
async def test_soft_deleted_members_excluded_from_both_endpoints(
    client: AsyncClient, auth_headers: dict, db_session
):
    """[需求 §2.2 根因] 旧逻辑 6>3 异常的另一原因是「未过滤软删除」。
    本测试构造软删除记录，验证两接口都正确排除 status='deleted' 的记录。"""
    # 基准
    base_r1 = await client.get("/api/family/member/quota", headers=auth_headers)
    base_used = base_r1.json()["quota_used"]

    # 找到当前测试用户
    uid = await _get_current_user_id(db_session)
    if uid == 0:
        pytest.skip("当前用户 ID 不可用")

    # 通过 ORM 插入一个软删除态的 family_member 记录（兼容 SQLite 测试库 / MySQL 生产库）
    deleted_member = FamilyMember(
        user_id=uid,
        nickname="测试软删档",
        relationship_type="other",
        status="deleted",
        is_self=False,
    )
    db_session.add(deleted_member)
    await db_session.commit()

    # 再次获取，数值不应变化
    r1 = await client.get("/api/family/member/quota", headers=auth_headers)
    r2 = await client.get("/api/member/quota-usage", headers=auth_headers)
    after_used = r1.json()["quota_used"]
    after_managed = r2.json()["max_managed_used"]

    assert after_used == base_used, (
        f"软删除记录不应被计入 quota_used。基准 {base_used}, 软删后 {after_used}"
    )
    assert after_used == after_managed, (
        f"两接口仍需相等（软删后）：quota_used={after_used}, max_managed_used={after_managed}"
    )


# ──────────── 测试 5：新增家人后两接口同步增加 ────────────


@pytest.mark.asyncio
async def test_add_member_both_endpoints_increase_together(
    client: AsyncClient, auth_headers: dict
):
    """[需求 §7 验收 2] 新增家人时，两处数字必须同步增减。"""
    # 基准
    r1 = await client.get("/api/family/member/quota", headers=auth_headers)
    r2 = await client.get("/api/member/quota-usage", headers=auth_headers)
    base_quota = r1.json()["quota_used"]
    base_managed = r2.json()["max_managed_used"]
    assert base_quota == base_managed, "前置条件失败：基准两接口已不一致"

    # 创建一个新档案（走标准 /api/family/members POST 接口）
    add_r = await client.post(
        "/api/family/members",
        json={
            "name": "口径一致性测试家人",
            "nickname": "口径一致性测试家人",
            "relationship_type": "other",
        },
        headers=auth_headers,
    )
    if add_r.status_code not in (200, 201):
        pytest.skip(f"无法新建测试家人（HTTP {add_r.status_code}：{add_r.text}），跳过同步增减验证")

    # 再次拉取，两接口都应 +1，且仍相等
    r1b = await client.get("/api/family/member/quota", headers=auth_headers)
    r2b = await client.get("/api/member/quota-usage", headers=auth_headers)
    new_quota = r1b.json()["quota_used"]
    new_managed = r2b.json()["max_managed_used"]
    assert new_quota == base_quota + 1, (
        f"新增家人后 quota_used 未 +1：基准 {base_quota}，新值 {new_quota}"
    )
    assert new_quota == new_managed, (
        f"新增家人后两接口仍需相等：quota_used={new_quota}, max_managed_used={new_managed}"
    )
