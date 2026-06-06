"""[BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V4 2026-06-03] FamilyMember.status 治本 v4 回归测试

覆盖范围：
  事件 1: 邀请过期           → status='unbound', sub_status='invited_expired'
  事件 2: 对方拒绝邀请       → status='unbound', sub_status='rejected'
  事件 3: 守护关系取消       → status='unbound', sub_status='unbinded'
  堵漏 #7: POST /api/family/members 不允许 member_user_id 直建绑定（400）
  堵漏 #8: DELETE /api/family/members/{id} 在 status='bound' 时拒绝（400）

测试入口：
  · service 级别原子用例：直接调 family_member_status_rollback 函数 + db_session
  · 路由级别用例：直接调用 family.add_family_member / remove_family_member 路由函数

依赖项目自带 conftest（db_session 来自内存 SQLite，AsyncSession）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


# ─────────────── 内置 user fixtures（避免依赖外部 conftest） ───────────────


@pytest_asyncio.fixture
async def current_user(db_session):
    from app.models.models import User
    from app.core.security import get_password_hash
    user = User(
        phone=f"+86_v4_{int(datetime.now().timestamp() * 1000) % 10_000_000}",
        password_hash=get_password_hash("test123"),
        nickname="测试用户A",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session):
    from app.models.models import User
    from app.core.security import get_password_hash
    user = User(
        phone=f"+86_v4o_{int(datetime.now().timestamp() * 1000) % 10_000_000}",
        password_hash=get_password_hash("test123"),
        nickname="测试用户B",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ─────────────── 工具函数 ───────────────

async def _make_member_bound(db, *, user_id, member_user_id=None, nickname="测试家人"):
    from app.models.models import FamilyMember
    m = FamilyMember(
        user_id=user_id,
        member_user_id=member_user_id,
        nickname=nickname,
        relationship_type="other",
        is_self=False,
        status="bound",
        sub_status="bound",
    )
    db.add(m)
    await db.flush()
    await db.commit()
    return m


async def _make_member_unbound(db, *, user_id, nickname="未绑定家人"):
    from app.models.models import FamilyMember
    m = FamilyMember(
        user_id=user_id,
        nickname=nickname,
        relationship_type="other",
        is_self=False,
        status="unbound",
        sub_status="not_applied",
    )
    db.add(m)
    await db.flush()
    await db.commit()
    return m


async def _make_invitation_pending(db, *, inviter_user_id, member_id, expires_in_seconds=86400):
    from app.models.models import FamilyInvitation
    inv = FamilyInvitation(
        invite_code=f"test_v4_{member_id}_{datetime.now().timestamp()}",
        inviter_user_id=inviter_user_id,
        member_id=member_id,
        status="pending",
        expires_at=datetime.now() + timedelta(seconds=expires_in_seconds),
    )
    db.add(inv)
    await db.flush()
    await db.commit()
    return inv


async def _make_mgmt_active(db, *, manager_user_id, managed_user_id, managed_member_id):
    from app.models.models import FamilyManagement
    mg = FamilyManagement(
        manager_user_id=manager_user_id,
        managed_user_id=managed_user_id,
        managed_member_id=managed_member_id,
        status="active",
    )
    db.add(mg)
    await db.flush()
    await db.commit()
    return mg


# ─────────────── 事件 1：邀请过期 ───────────────

class TestInvitationExpiredV4:
    async def test_member_rolled_back_to_unbound(self, db_session, current_user):
        member = await _make_member_bound(db_session, user_id=current_user.id)
        inv = await _make_invitation_pending(
            db_session, inviter_user_id=current_user.id, member_id=member.id,
            expires_in_seconds=-1,
        )

        from app.services.family_member_status_rollback import (
            rollback_member_for_invitation_event, EVENT_INVITATION_EXPIRED,
        )
        inv.status = "expired"
        await rollback_member_for_invitation_event(db_session, inv, EVENT_INVITATION_EXPIRED)
        await db_session.commit()

        await db_session.refresh(member)
        assert member.status == "unbound"
        assert member.sub_status == "invited_expired"


# ─────────────── 事件 2：邀请拒绝 ───────────────

class TestInvitationRejectedV4:
    async def test_member_rolled_back_to_unbound(self, db_session, current_user):
        member = await _make_member_bound(db_session, user_id=current_user.id)
        inv = await _make_invitation_pending(
            db_session, inviter_user_id=current_user.id, member_id=member.id,
        )

        from app.services.family_member_status_rollback import (
            rollback_member_for_invitation_event, EVENT_INVITATION_REJECTED,
        )
        inv.status = "cancelled"
        await rollback_member_for_invitation_event(db_session, inv, EVENT_INVITATION_REJECTED)
        await db_session.commit()

        await db_session.refresh(member)
        assert member.status == "unbound"
        assert member.sub_status == "rejected"


# ─────────────── 事件 3：守护关系取消 ───────────────

class TestManagementCancelledV4:
    async def test_member_rolled_back_on_cancel(self, db_session, current_user, other_user):
        member = await _make_member_bound(
            db_session, user_id=current_user.id, member_user_id=other_user.id,
        )
        mg = await _make_mgmt_active(
            db_session,
            manager_user_id=current_user.id,
            managed_user_id=other_user.id,
            managed_member_id=member.id,
        )

        from app.services.family_member_status_rollback import (
            rollback_member_for_management_cancel,
        )
        mg.status = "cancelled"
        await rollback_member_for_management_cancel(
            db_session,
            manager_user_id=mg.manager_user_id,
            managed_member_id=mg.managed_member_id,
        )
        await db_session.commit()

        await db_session.refresh(member)
        assert member.status == "unbound"
        assert member.sub_status == "unbinded"


# ─────────────── 防御性堵漏 #7：禁止 member_user_id 直建绑定 ───────────────

class TestForbidDirectBindV4:
    async def test_add_member_with_member_user_id_rejected(self, db_session, current_user, other_user):
        from fastapi import HTTPException
        from app.api.family import add_family_member
        from app.schemas.user import FamilyMemberCreate

        data = FamilyMemberCreate(
            nickname="测试",
            member_user_id=other_user.id,
            relationship_type="other",
        )
        with pytest.raises(HTTPException) as exc:
            await add_family_member(data=data, current_user=current_user, db=db_session)
        assert exc.value.status_code == 400


# ─────────────── 防御性堵漏 #8：bound 状态拒绝删除 ───────────────

class TestForbidDeleteBoundV4:
    async def test_delete_bound_member_rejected(self, db_session, current_user):
        from fastapi import HTTPException
        from app.api.family import remove_family_member

        member = await _make_member_bound(db_session, user_id=current_user.id)
        with pytest.raises(HTTPException) as exc:
            await remove_family_member(member_id=member.id, current_user=current_user, db=db_session)
        assert exc.value.status_code == 400
        assert ("解除" in str(exc.value.detail)) or ("绑定" in str(exc.value.detail))

    async def test_delete_unbound_member_ok(self, db_session, current_user):
        from app.api.family import remove_family_member
        member = await _make_member_unbound(db_session, user_id=current_user.id)
        result = await remove_family_member(
            member_id=member.id, current_user=current_user, db=db_session,
        )
        assert "message" in result
        await db_session.refresh(member)
        assert member.status == "deleted"


# ─────────────── derive_v3_state 简化版恒等映射 ───────────────

class TestDeriveV3StateIsIdentityAfterCureV4:
    async def test_clean_bound_returns_bound(self, db_session, current_user):
        member = await _make_member_bound(db_session, user_id=current_user.id)
        from app.services.family_member_status import derive_v3_state
        v3 = await derive_v3_state(db_session, member=member)
        assert v3["main_status"] == "bound"
        assert v3["sub_status"] == "bound"

    async def test_clean_unbound_returns_same_sub_status(self, db_session, current_user):
        from app.models.models import FamilyMember
        m = FamilyMember(
            user_id=current_user.id,
            nickname="未绑定家人",
            relationship_type="other",
            is_self=False,
            status="unbound",
            sub_status="invited_expired",
        )
        db_session.add(m)
        await db_session.flush()
        await db_session.commit()
        from app.services.family_member_status import derive_v3_state
        v3 = await derive_v3_state(db_session, member=m)
        assert v3["main_status"] == "unbound"
        assert v3["sub_status"] == "invited_expired"
        assert v3["can_reinvite"] is True
