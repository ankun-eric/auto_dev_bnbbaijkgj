"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29] 守护人体系 v1.3.2 补丁测试

PRD 测试用例（仅后端可覆盖部分）：
- TC-G2-01~05：配额公式（蚂蚁阿福派补丁版） _calc_used_quota()
- TC-G3-01：/api/family/members 返回 target_left 字段（已存在 v1 接口字段，本次回归）
- TC-G1-05：邀请 nickname 入库（已在 v1 测试覆盖，本次再回归）
"""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    User,
    UserRole,
)


async def _make_user(phone: str, nickname: str = "用户") -> int:
    async with test_session() as s:
        u = User(
            phone=phone,
            password_hash=get_password_hash("p123"),
            nickname=nickname,
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        # 同步建一条 is_self=True 的 family_member（与登录注册流程一致）
        s.add(FamilyMember(
            user_id=uid,
            nickname=nickname,
            relationship_type="本人",
            is_self=True,
            avatar_color_index=0,
        ))
        await s.commit()
        return uid


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post("/api/auth/login", json={"phone": phone, "password": "p123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """每个测试用例自动清空频次计数器（避免 5 次/天上限干扰）"""
    try:
        from app.api.guardian_bugfix_v1 import reset_rate_limit_for_test
        reset_rate_limit_for_test(None)
        yield
        reset_rate_limit_for_test(None)
    except Exception:
        yield


# ─────────────────────────────────────────────────────────────
# TC-G2: 配额公式 _calc_used_quota
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tc_g2_01_only_self_used_zero(client: AsyncClient):
    """TC-G2-01：仅有本人 → 配额已用 = 0"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    res = await client.get("/api/guardian/v13/family/list", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["used"] == 0, f"仅本人时 used 应为 0，实际：{body}"


@pytest.mark.asyncio
async def test_tc_g2_02_pending_invitation_occupies_quota(client: AsyncClient):
    """TC-G2-02：创建 2 条悬空 pending 邀请 → used 增加 2

    用户原话：'蚂蚁阿福派补丁版'公式 — pending（未过期）必须占名额。
    """
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 初始
    res0 = await client.get("/api/guardian/v13/family/list", headers=h)
    base_used = res0.json()["used"]

    # 创建 2 条悬空 pending 邀请（无 member_id）
    for i in range(2):
        r = await client.post(
            "/api/family/invitation",
            json={"relation_type": "父亲", "nickname": f"新邀请{i}"},
            headers=h,
        )
        assert r.status_code == 200, r.text

    res = await client.get("/api/guardian/v13/family/list", headers=h)
    body = res.json()
    assert body["used"] == base_used + 2, (
        f"创建 2 条悬空 pending 后 used 应为 {base_used + 2}，实际：{body['used']}"
    )


@pytest.mark.asyncio
async def test_tc_g2_03_cancel_pending_releases_quota(client: AsyncClient):
    """TC-G2-03：撤回（cancelled）一条悬空 pending → used -1"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 先创建 2 条
    codes = []
    for i in range(2):
        r = await client.post(
            "/api/family/invitation",
            json={"relation_type": "父亲", "nickname": f"X{i}"},
            headers=h,
        )
        assert r.status_code == 200
        codes.append(r.json()["invite_code"])

    res_before = await client.get("/api/guardian/v13/family/list", headers=h)
    used_before = res_before.json()["used"]

    # 把第一条撤销
    async with test_session() as s:
        inv = (await s.execute(
            select(FamilyInvitation).where(FamilyInvitation.invite_code == codes[0])
        )).scalar_one()
        inv.status = "cancelled"
        await s.commit()

    res_after = await client.get("/api/guardian/v13/family/list", headers=h)
    used_after = res_after.json()["used"]
    assert used_after == used_before - 1, (
        f"撤销 1 条 pending 后 used 应减少 1，实际 {used_before} → {used_after}"
    )


@pytest.mark.asyncio
async def test_tc_g2_04_expired_pending_does_not_occupy(client: AsyncClient):
    """TC-G2-04：悬空 pending 自然过期（expires_at < now）→ 不占配额"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 直接构造一条已过期的 pending
    async with test_session() as s:
        s.add(FamilyInvitation(
            invite_code=uuid.uuid4().hex,
            inviter_user_id=uid,
            member_id=None,
            status="pending",
            expires_at=datetime.now() - timedelta(hours=1),  # 已过期
            relation_type="父亲",
            nickname="过期邀请",
        ))
        await s.commit()

    res = await client.get("/api/guardian/v13/family/list", headers=h)
    body = res.json()
    assert body["used"] == 0, f"已过期 pending 不应占配额，实际 used={body['used']}"


@pytest.mark.asyncio
async def test_tc_g2_05_repeated_invite_cancel_no_drift(client: AsyncClient):
    """TC-G2-05：反复邀请-取消压测 → used 始终 0~max 范围内，不出现负数 / 刷穿"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 反复 5 轮 — 创建 + 立即撤销
    # 注意：B7 频次防护是 5 次/天，所以只压测 4 轮以保留余地（且 reset_rate_limit_for_test fixture 会清空）
    for round_i in range(4):
        r = await client.post(
            "/api/family/invitation",
            json={"relation_type": "父亲", "nickname": f"R{round_i}"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        code = r.json()["invite_code"]

        # 撤销
        async with test_session() as s:
            inv = (await s.execute(
                select(FamilyInvitation).where(FamilyInvitation.invite_code == code)
            )).scalar_one()
            inv.status = "cancelled"
            await s.commit()

        res = await client.get("/api/guardian/v13/family/list", headers=h)
        used = res.json()["used"]
        assert 0 <= used <= 99, f"第{round_i + 1}轮 used 异常：{used}"

    # 最后一轮压测后：used 应为 0（所有 pending 都被撤销）
    res_final = await client.get("/api/guardian/v13/family/list", headers=h)
    assert res_final.json()["used"] == 0


# ─────────────────────────────────────────────────────────────
# TC-G3: /api/family/members 已带 target_left（回归）
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tc_g3_members_target_left_present(client: AsyncClient):
    """TC-G3-后端：/api/family/members 在 cancelled_by_target 状态下返回 target_left=true"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    uid = await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 创建一条已绑定的家人（family_member）+ FamilyManagement(active)，
    # 然后将 mgmt 改为 cancelled_by_target
    async with test_session() as s:
        managed_phone = f"+8613{uuid.uuid4().hex[:8]}"
        managed_user = User(
            phone=managed_phone,
            password_hash=get_password_hash("p123"),
            nickname="被守护人B",
            role=UserRole.user,
        )
        s.add(managed_user)
        await s.flush()
        m = FamilyMember(
            user_id=uid,
            nickname="B-mem",
            relationship_type="父亲",
            is_self=False,
            member_user_id=managed_user.id,
            avatar_color_index=2,
        )
        s.add(m)
        await s.flush()
        s.add(FamilyManagement(
            manager_user_id=uid,
            managed_user_id=managed_user.id,
            managed_member_id=m.id,
            status="cancelled_by_target",
            is_primary_guardian=True,
        ))
        await s.commit()
        mid = m.id

    res = await client.get("/api/family/members", headers=h)
    assert res.status_code == 200, res.text
    items = res.json().get("items", [])
    target = next((x for x in items if x.get("id") == mid), None)
    assert target is not None, f"应返回 mid={mid} 的家人卡片，实际 items: {items}"
    assert target.get("target_left") is True, (
        f"cancelled_by_target → target_left 应为 true，实际：{target}"
    )
