"""[BUGFIX-FAMILY-DUPLICATE-BIND-V1 2026-06-02] 家庭成员重复绑定 BUG 修复测试

覆盖用例：
- TC-01：S1 扫 A 成功 → S1 再扫 B（同管理者）被拦，返回 400 + 文案
- TC-02：S2 扫 B 正常成功（不误伤其他人）
- TC-03：S1 接受【另一个管理者】的邀请正常成功（不做全局唯一）
- TC-04：S1 解绑 A 后再扫 B 应能成功（解绑后释放坑位）
- TC-05：手机号相同但用户 ID 不同的情况也能被判为同一人并拦截
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
    HealthProfile,
    User,
    UserRole,
)

DUPLICATE_DETAIL = "您已是该家庭的成员，无法重复绑定。"


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
        await s.commit()
        return uid


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post("/api/auth/login", json={"phone": phone, "password": "p123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _create_member_and_invite(manager_uid: int, member_nickname: str) -> str:
    """在 manager 名下创建一个 FamilyMember（含 HealthProfile）并生成一条 pending 邀请，返回 invite_code。"""
    async with test_session() as s:
        m = FamilyMember(
            user_id=manager_uid,
            nickname=member_nickname,
            relationship_type="other",
            is_self=False,
            avatar_color_index=1,
        )
        s.add(m)
        await s.flush()
        hp = HealthProfile(
            user_id=manager_uid,
            family_member_id=m.id,
            name=member_nickname,
        )
        s.add(hp)
        await s.flush()

        code = uuid.uuid4().hex
        inv = FamilyInvitation(
            invite_code=code,
            inviter_user_id=manager_uid,
            member_id=m.id,
            relation_type="other",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        s.add(inv)
        await s.commit()
        return code


async def _accept(client: AsyncClient, headers: dict, code: str):
    return await client.post(f"/api/family/invitation/{code}/accept", json={}, headers=headers)


@pytest.mark.asyncio
async def test_tc01_same_manager_duplicate_bind_blocked(client: AsyncClient):
    """TC-01：S1 扫 A 成功后，再扫同管理者的 B 被拦截，返回 400 + 指定文案。"""
    mgr_phone = f"+8613{uuid.uuid4().hex[:8]}"
    s1_phone = f"+8613{uuid.uuid4().hex[:8]}"
    mgr_uid = await _make_user(mgr_phone, "管理者")
    await _make_user(s1_phone, "客户S1")

    code_a = await _create_member_and_invite(mgr_uid, "成员A")
    code_b = await _create_member_and_invite(mgr_uid, "成员B")

    s1_headers = await _headers(client, s1_phone)

    res_a = await _accept(client, s1_headers, code_a)
    assert res_a.status_code == 200, res_a.text

    res_b = await _accept(client, s1_headers, code_b)
    assert res_b.status_code == 400, res_b.text
    assert res_b.json()["detail"] == DUPLICATE_DETAIL


@pytest.mark.asyncio
async def test_tc02_other_user_not_blocked(client: AsyncClient):
    """TC-02：S2 扫 B 正常成功，不误伤其他人。"""
    mgr_phone = f"+8613{uuid.uuid4().hex[:8]}"
    s1_phone = f"+8613{uuid.uuid4().hex[:8]}"
    s2_phone = f"+8613{uuid.uuid4().hex[:8]}"
    mgr_uid = await _make_user(mgr_phone, "管理者")
    await _make_user(s1_phone, "客户S1")
    await _make_user(s2_phone, "客户S2")

    code_a = await _create_member_and_invite(mgr_uid, "成员A")
    code_b = await _create_member_and_invite(mgr_uid, "成员B")

    s1_headers = await _headers(client, s1_phone)
    s2_headers = await _headers(client, s2_phone)

    assert (await _accept(client, s1_headers, code_a)).status_code == 200
    # S2 扫 B 应成功
    res = await _accept(client, s2_headers, code_b)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_tc03_other_manager_not_blocked(client: AsyncClient):
    """TC-03：S1 接受另一个管理者的邀请正常成功，不做全局唯一。"""
    mgr1_phone = f"+8613{uuid.uuid4().hex[:8]}"
    mgr2_phone = f"+8613{uuid.uuid4().hex[:8]}"
    s1_phone = f"+8613{uuid.uuid4().hex[:8]}"
    mgr1_uid = await _make_user(mgr1_phone, "管理者1")
    mgr2_uid = await _make_user(mgr2_phone, "管理者2")
    await _make_user(s1_phone, "客户S1")

    code_a = await _create_member_and_invite(mgr1_uid, "成员A")
    code_x = await _create_member_and_invite(mgr2_uid, "成员X")

    s1_headers = await _headers(client, s1_phone)

    assert (await _accept(client, s1_headers, code_a)).status_code == 200
    # 接受另一个管理者的邀请应成功
    res = await _accept(client, s1_headers, code_x)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_tc04_rebind_after_unbind(client: AsyncClient):
    """TC-04：S1 解绑 A 后再扫 B 应能成功（解绑后释放坑位）。"""
    mgr_phone = f"+8613{uuid.uuid4().hex[:8]}"
    s1_phone = f"+8613{uuid.uuid4().hex[:8]}"
    mgr_uid = await _make_user(mgr_phone, "管理者")
    s1_uid = await _make_user(s1_phone, "客户S1")

    code_a = await _create_member_and_invite(mgr_uid, "成员A")
    code_b = await _create_member_and_invite(mgr_uid, "成员B")

    s1_headers = await _headers(client, s1_phone)
    assert (await _accept(client, s1_headers, code_a)).status_code == 200

    # 模拟解绑 A：将对应 active 绑定置为 cancelled
    async with test_session() as s:
        rows = await s.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == mgr_uid,
                FamilyManagement.managed_user_id == s1_uid,
                FamilyManagement.status == "active",
            )
        )
        for fm in rows.scalars():
            fm.status = "cancelled"
        await s.commit()

    # 解绑后再扫 B 应成功
    res = await _accept(client, s1_headers, code_b)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_tc05_same_phone_different_user_blocked():
    """TC-05：手机号相同但用户 ID 不同也能被判为同一人并拦截。

    User.phone 列带 unique 约束，无法让两个账号同时拥有同一手机号；
    且"同一人换了账号但手机号一致"在真实场景中是旧号释放后新号复用同手机号。
    因此本用例直接对 service 层 is_duplicate_bind 做单元测试，验证手机号维度判重：
    管理者名下已有一条 active 绑定指向被守护人 S1（phone=shared），
    现以另一个不同 ID 但 phone=shared 的接受者去判重，应返回 True（命中手机号维度）。
    """
    from app.services.family_bind_dedup_service import is_duplicate_bind

    shared_phone = f"+8613{uuid.uuid4().hex[:8]}"
    async with test_session() as s:
        mgr = User(phone=f"+8613{uuid.uuid4().hex[:8]}", password_hash=get_password_hash("p123"),
                   nickname="管理者", role=UserRole.user)
        s1 = User(phone=shared_phone, password_hash=get_password_hash("p123"),
                  nickname="客户S1", role=UserRole.user)
        s.add_all([mgr, s1])
        await s.flush()
        # 已有一条管理者名下 active 绑定，被守护人为 S1（phone=shared）
        s.add(FamilyManagement(
            manager_user_id=mgr.id,
            managed_user_id=s1.id,
            status="active",
        ))
        await s.flush()

        # 一个不同 user_id（不存在于绑定中）但手机号与 S1 相同的接受者
        dup = await is_duplicate_bind(
            s,
            manager_user_id=mgr.id,
            managed_user_id=999999,  # 不同的用户 ID，精确维度不命中
            managed_phone=shared_phone,  # 手机号与已绑定的 S1 相同 → 应命中
        )
        assert dup is True

        # 反例：不同管理者名下不应误伤（全局唯一关闭）
        not_dup = await is_duplicate_bind(
            s,
            manager_user_id=888888,  # 另一个管理者
            managed_user_id=999999,
            managed_phone=shared_phone,
        )
        assert not_dup is False
