"""[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 健康档案首页双卡片优化 - 后端自动化测试

覆盖：
1. /api/reverse-guardian/guardian-count 返回字段：
   max_guardians_for_me / max_guardians_by_me / bound_others_count /
   is_top_level / is_unlimited / member_level
2. /api/reverse-guardian/my-guardians 返回 active + pending 项
3. /api/reverse-guardian/invite/cancel 新接口
4. 反向邀请 X<Y 校验，返回 GUARDIAN_LIMIT_REACHED
5. 「我守护的人」邀请超额返回 WARD_LIMIT_REACHED
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.models import (
    FamilyManagement,
    FamilyInvitation,
    ReverseGuardianInvitation,
    User,
)
from app.models.membership_plan import FreeMemberQuota, MembershipPlan, UserMembershipSub
from tests.conftest import test_session


async def _register_and_login(client: AsyncClient, phone: str, nickname: str) -> dict:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "pass1234", "nickname": nickname,
    })
    resp = await client.post("/api/auth/login", json={
        "phone": phone, "password": "pass1234",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _get_user_id(headers: dict, client: AsyncClient) -> int:
    resp = await client.get("/api/auth/me", headers=headers)
    return resp.json()["id"]


async def _ensure_free_quota(max_managed=3, max_managed_by=3):
    async with test_session() as session:
        from sqlalchemy import select
        existing = (await session.execute(
            select(FreeMemberQuota).where(FreeMemberQuota.id == 1)
        )).scalar_one_or_none()
        if existing:
            existing.max_managed = max_managed
            existing.max_managed_by = max_managed_by
        else:
            session.add(FreeMemberQuota(
                id=1,
                max_managed=max_managed,
                max_managed_by=max_managed_by,
                ai_outbound_call_count=5,
                emergency_ai_call_count=3,
            ))
        await session.commit()


# ──────────────────────────────────────────────────────────
# guardian-count 新字段
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dualcard_001_guardian_count_fields(client: AsyncClient, auth_headers):
    """TC-DUALCARD-001: guardian-count 返回新字段。"""
    await _ensure_free_quota(3, 3)
    resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # 新字段都存在
    assert "max_guardians_for_me" in data
    assert "max_guardians_by_me" in data
    assert "bound_others_count" in data
    assert "is_top_level" in data
    assert "is_unlimited" in data
    assert "member_level" in data
    # 免费会员默认值
    assert data["max_guardians_for_me"] == 3
    assert data["max_guardians_by_me"] == 3
    assert data["is_top_level"] is False
    assert data["is_unlimited"] is False
    assert data["bound_others_count"] == 0
    assert data["total_count"] == 0
    assert data["active_count"] == 0
    assert data["pending_count"] == 0


@pytest.mark.asyncio
async def test_dualcard_002_guardian_count_with_active(client: AsyncClient, auth_headers):
    """TC-DUALCARD-002: 已有 active 守护关系时 active_count / total_count 正确。"""
    await _ensure_free_quota(3, 3)
    user_id = await _get_user_id(auth_headers, client)
    headers_b = await _register_and_login(client, "13900000002", "守护者B")
    uid_b = await _get_user_id(headers_b, client)
    async with test_session() as s:
        s.add(FamilyManagement(
            manager_user_id=uid_b, managed_user_id=user_id, status="active",
        ))
        await s.commit()

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_count"] == 1
    assert data["total_count"] == 1


# ──────────────────────────────────────────────────────────
# my-guardians 返回 active + pending
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dualcard_003_my_guardians_pending_items(client: AsyncClient, auth_headers):
    """TC-DUALCARD-003: my-guardians 包含 pending 邀请项。"""
    await _ensure_free_quota(3, 3)
    user_id = await _get_user_id(auth_headers, client)
    # 直接插入一条 pending 反向邀请
    async with test_session() as s:
        s.add(ReverseGuardianInvitation(
            invite_code="testcode001",
            invitee_user_id=user_id,
            status="pending",
            max_uses=3,
            used_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            relation_type="儿子",
        ))
        await s.commit()

    resp = await client.get("/api/reverse-guardian/my-guardians", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_count"] == 1
    assert data["active_count"] == 0
    items = data["items"]
    pending = [it for it in items if it.get("item_type") == "pending"]
    assert len(pending) == 1
    assert pending[0]["invite_code"] == "testcode001"
    assert pending[0]["invitation_id"] is not None


# ──────────────────────────────────────────────────────────
# 取消邀请接口
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dualcard_004_cancel_invite_success(client: AsyncClient, auth_headers):
    """TC-DUALCARD-004: 取消反向邀请成功，名额释放。"""
    await _ensure_free_quota(3, 3)
    user_id = await _get_user_id(auth_headers, client)
    async with test_session() as s:
        inv = ReverseGuardianInvitation(
            invite_code="cancelcode001",
            invitee_user_id=user_id,
            status="pending",
            max_uses=3, used_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        s.add(inv)
        await s.commit()
        await s.refresh(inv)
        inv_id = inv.id

    resp = await client.post(
        "/api/reverse-guardian/invite/cancel",
        headers=auth_headers,
        json={"invitation_id": inv_id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    # 再查 count，pending 应该 -1
    count_resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert count_resp.json()["pending_count"] == 0


@pytest.mark.asyncio
async def test_dualcard_005_cancel_invite_by_code(client: AsyncClient, auth_headers):
    """TC-DUALCARD-005: 通过 invite_code 取消邀请。"""
    await _ensure_free_quota(3, 3)
    user_id = await _get_user_id(auth_headers, client)
    async with test_session() as s:
        s.add(ReverseGuardianInvitation(
            invite_code="cancelcode002",
            invitee_user_id=user_id,
            status="pending",
            max_uses=3, used_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        ))
        await s.commit()

    resp = await client.post(
        "/api/reverse-guardian/invite/cancel",
        headers=auth_headers,
        json={"invite_code": "cancelcode002"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_dualcard_006_cancel_invite_not_found(client: AsyncClient, auth_headers):
    """TC-DUALCARD-006: 取消不存在的邀请，404。"""
    resp = await client.post(
        "/api/reverse-guardian/invite/cancel",
        headers=auth_headers,
        json={"invitation_id": 99999},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dualcard_007_cancel_invite_not_owner(client: AsyncClient, auth_headers):
    """TC-DUALCARD-007: 取消他人邀请，403。"""
    await _ensure_free_quota(3, 3)
    headers_b = await _register_and_login(client, "13900000003", "用户B")
    uid_b = await _get_user_id(headers_b, client)
    async with test_session() as s:
        inv = ReverseGuardianInvitation(
            invite_code="othercode",
            invitee_user_id=uid_b,  # B 的邀请
            status="pending",
            max_uses=3, used_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        s.add(inv)
        await s.commit()
        await s.refresh(inv)
        inv_id = inv.id

    # A 尝试取消 B 的邀请
    resp = await client.post(
        "/api/reverse-guardian/invite/cancel",
        headers=auth_headers,
        json={"invitation_id": inv_id},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dualcard_008_cancel_invite_already_cancelled(client: AsyncClient, auth_headers):
    """TC-DUALCARD-008: 已取消的邀请不可再次取消，400。"""
    await _ensure_free_quota(3, 3)
    user_id = await _get_user_id(auth_headers, client)
    async with test_session() as s:
        inv = ReverseGuardianInvitation(
            invite_code="alreadycancel",
            invitee_user_id=user_id,
            status="cancelled",
            max_uses=3, used_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        s.add(inv)
        await s.commit()
        await s.refresh(inv)
        inv_id = inv.id

    resp = await client.post(
        "/api/reverse-guardian/invite/cancel",
        headers=auth_headers,
        json={"invitation_id": inv_id},
    )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────
# 反向邀请 X<Y 校验：GUARDIAN_LIMIT_REACHED
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dualcard_009_reverse_invite_limit_reached(client: AsyncClient, auth_headers):
    """TC-DUALCARD-009: X=Y 时邀请返回 GUARDIAN_LIMIT_REACHED。"""
    await _ensure_free_quota(3, 1)  # 设置 max_managed_by=1
    user_id = await _get_user_id(auth_headers, client)
    headers_b = await _register_and_login(client, "13900000004", "守护者B")
    uid_b = await _get_user_id(headers_b, client)
    # 已有 1 个 active，达到上限 1
    async with test_session() as s:
        s.add(FamilyManagement(
            manager_user_id=uid_b, managed_user_id=user_id, status="active",
        ))
        await s.commit()

    # 尝试发反向邀请，应被拦截
    resp = await client.post(
        "/api/reverse-guardian/invite",
        headers=auth_headers,
        json={"relation_type": "其他"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == "GUARDIAN_LIMIT_REACHED"
    assert detail["x"] == 1
    assert detail["y"] == 1


@pytest.mark.asyncio
async def test_dualcard_010_reverse_invite_not_yet_full(client: AsyncClient, auth_headers):
    """TC-DUALCARD-010: X<Y 时正常发邀请。"""
    await _ensure_free_quota(3, 3)
    resp = await client.post(
        "/api/reverse-guardian/invite",
        headers=auth_headers,
        json={"relation_type": "儿子"},
    )
    assert resp.status_code == 200, resp.text
    assert "invite_code" in resp.json()


# ──────────────────────────────────────────────────────────
# 我守护的人 邀请 X<Y 校验：WARD_LIMIT_REACHED
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dualcard_011_ward_invite_limit_reached(client: AsyncClient, auth_headers):
    """TC-DUALCARD-011: 我守护的人 X=Y 时邀请返回 WARD_LIMIT_REACHED。"""
    await _ensure_free_quota(1, 3)  # max_managed=1
    user_id = await _get_user_id(auth_headers, client)
    # 创建 1 个被守护人 active，达到上限
    headers_c = await _register_and_login(client, "13900000005", "被守护C")
    uid_c = await _get_user_id(headers_c, client)
    async with test_session() as s:
        s.add(FamilyManagement(
            manager_user_id=user_id, managed_user_id=uid_c, status="active",
        ))
        await s.commit()

    # 尝试新建邀请
    resp = await client.post(
        "/api/family/invitation",
        headers=auth_headers,
        json={"relation_type": "father"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == "WARD_LIMIT_REACHED"
    assert detail["x"] == 1
    assert detail["y"] == 1


# ──────────────────────────────────────────────────────────
# 顶级会员判定
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dualcard_012_top_level_member(client: AsyncClient, auth_headers):
    """TC-DUALCARD-012: 顶级会员 is_top_level=True。"""
    await _ensure_free_quota(3, 3)
    user_id = await _get_user_id(auth_headers, client)
    async with test_session() as s:
        plan_basic = MembershipPlan(
            name="基础会员",
            max_managed=3, max_managed_by=3,
            ai_outbound_call_count=10, emergency_ai_call_count=5,
            is_active=True, is_recommended=False, sort_order=1,
        )
        plan_top = MembershipPlan(
            name="顶级会员",
            max_managed=10, max_managed_by=10,
            ai_outbound_call_count=100, emergency_ai_call_count=50,
            is_active=True, is_recommended=True, sort_order=2,
        )
        s.add_all([plan_basic, plan_top])
        await s.commit()
        await s.refresh(plan_top)
        # 订阅顶级
        s.add(UserMembershipSub(
            user_id=user_id, plan_id=plan_top.id,
            billing_cycle="monthly",
            start_at=datetime.utcnow(),
            expire_at=datetime.utcnow() + timedelta(days=30),
            status="active",
        ))
        await s.commit()

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_top_level"] is True
    assert data["max_guardians_for_me"] == 10
    assert data["max_guardians_by_me"] == 10
    assert data["member_level"] == "顶级会员"


@pytest.mark.asyncio
async def test_dualcard_013_non_top_paid_member(client: AsyncClient, auth_headers):
    """TC-DUALCARD-013: 非顶级付费会员 is_top_level=False。"""
    await _ensure_free_quota(3, 3)
    user_id = await _get_user_id(auth_headers, client)
    async with test_session() as s:
        plan_basic = MembershipPlan(
            name="基础会员",
            max_managed=5, max_managed_by=5,
            ai_outbound_call_count=10, emergency_ai_call_count=5,
            is_active=True, is_recommended=False, sort_order=1,
        )
        plan_top = MembershipPlan(
            name="顶级会员",
            max_managed=10, max_managed_by=10,
            ai_outbound_call_count=100, emergency_ai_call_count=50,
            is_active=True, is_recommended=True, sort_order=2,
        )
        s.add_all([plan_basic, plan_top])
        await s.commit()
        await s.refresh(plan_basic)
        s.add(UserMembershipSub(
            user_id=user_id, plan_id=plan_basic.id,
            billing_cycle="monthly",
            start_at=datetime.utcnow(),
            expire_at=datetime.utcnow() + timedelta(days=30),
            status="active",
        ))
        await s.commit()

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_top_level"] is False
    assert data["max_guardians_for_me"] == 5
