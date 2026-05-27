"""[IGUARD-V2 2026-05-28] 「我守护的人」页面 10 项 Bug 修复 - 自动化测试

覆盖：
- Bug 5：会员权益共享开关接口 share-toggle 与使用明细 usage-records
- Bug 6：解除守护接口 DELETE /api/family/management/{id} 双向通知
- Bug 8：移除接口的 invitation_id 参数 + can_remove 校验
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
    Notification,
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
        await s.commit()
        return uid


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post("/api/auth/login", json={"phone": phone, "password": "p123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _make_management(manager_phone: str, managed_phone: str) -> int:
    async with test_session() as s:
        manager = (await s.execute(select(User).where(User.phone == manager_phone))).scalar_one()
        managed = (await s.execute(select(User).where(User.phone == managed_phone))).scalar_one()
        m = FamilyMember(
            user_id=manager.id,
            nickname=managed.nickname or "家人",
            relationship_type="父亲",
            is_self=False,
            member_user_id=managed.id,
        )
        s.add(m)
        await s.flush()
        mgmt = FamilyManagement(
            manager_user_id=manager.id,
            managed_user_id=managed.id,
            managed_member_id=m.id,
            status="active",
            is_primary_guardian=True,
            priority_order=0,
            member_benefit_shared=True,
        )
        s.add(mgmt)
        await s.flush()
        mid = mgmt.id
        await s.commit()
        return mid


@pytest.mark.asyncio
async def test_share_toggle_enable_disable(client: AsyncClient):
    """[Bug 5] 测试共享额度开关：开 → 关 → 开"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    await _make_user(pb, "B")
    mgmt_id = await _make_management(pa, pb)
    h = await _headers(client, pa)

    res = await client.put(
        f"/api/family/management/{mgmt_id}/share-toggle",
        json={"enabled": False}, headers=h,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["member_benefit_shared"] is False

    res = await client.put(
        f"/api/family/management/{mgmt_id}/share-toggle",
        json={"enabled": True}, headers=h,
    )
    assert res.status_code == 200
    assert res.json()["member_benefit_shared"] is True


@pytest.mark.asyncio
async def test_share_toggle_only_manager(client: AsyncClient):
    """[Bug 5] 只有守护人可以操作开关"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    await _make_user(pb, "B")
    mgmt_id = await _make_management(pa, pb)
    h = await _headers(client, pb)  # 被守护人

    res = await client.put(
        f"/api/family/management/{mgmt_id}/share-toggle",
        json={"enabled": False}, headers=h,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_usage_records_quota_shape(client: AsyncClient):
    """[Bug 5] 使用明细接口返回 share_enabled / quota / items"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    await _make_user(pb, "B")
    mgmt_id = await _make_management(pa, pb)
    h = await _headers(client, pa)

    res = await client.get(f"/api/family/management/{mgmt_id}/usage-records?limit=10", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "share_enabled" in data
    assert "quota" in data and "total" in data["quota"]
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_delete_family_management_by_manager(client: AsyncClient):
    """[Bug 6] 守护人调用 DELETE /api/family/management/{id} 成功并产生双向通知"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    uid_a = await _make_user(pa, "A")
    uid_b = await _make_user(pb, "B")
    mgmt_id = await _make_management(pa, pb)
    h = await _headers(client, pa)

    res = await client.delete(f"/api/family/management/{mgmt_id}", headers=h)
    assert res.status_code == 200, res.text
    assert "已解除" in res.json()["message"]

    # 双向通知校验
    async with test_session() as s:
        notify_b = (await s.execute(
            select(Notification).where(Notification.user_id == uid_b)
        )).scalars().all()
        notify_a = (await s.execute(
            select(Notification).where(Notification.user_id == uid_a)
        )).scalars().all()
        assert any("解除" in (n.title or "") for n in notify_b)
        assert any("解除" in (n.title or "") for n in notify_a)


@pytest.mark.asyncio
async def test_remove_invitation_with_invitation_id(client: AsyncClient):
    """[Bug 8] 通过 invitation_id 移除纯邀请记录（已过期/已拒绝）"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    # 创建一条已过期的邀请
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == pa))).scalar_one()
        inv = FamilyInvitation(
            invite_code=uuid.uuid4().hex,
            inviter_user_id=u.id,
            status="expired",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            relation_type="父亲",
        )
        s.add(inv)
        await s.flush()
        inv_id = inv.id
        await s.commit()

    res = await client.post(
        "/api/guardian/v13/family/remove",
        json={"invitation_id": inv_id},
        headers=h,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("removed") is True
    assert body.get("type") == "invitation"


@pytest.mark.asyncio
async def test_remove_pending_active_invitation_returns_400(client: AsyncClient):
    """[Bug 8] pending 未过期的邀请直接移除应返回 400"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    h = await _headers(client, pa)

    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == pa))).scalar_one()
        inv = FamilyInvitation(
            invite_code=uuid.uuid4().hex,
            inviter_user_id=u.id,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=2),
            relation_type="母亲",
        )
        s.add(inv)
        await s.flush()
        inv_id = inv.id
        await s.commit()

    res = await client.post(
        "/api/guardian/v13/family/remove",
        json={"invitation_id": inv_id},
        headers=h,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_can_remove_field_in_list_response(client: AsyncClient):
    """[Bug 8] family/list 返回 can_remove 字段"""
    pa = f"+8613{uuid.uuid4().hex[:8]}"
    pb = f"+8613{uuid.uuid4().hex[:8]}"
    await _make_user(pa, "A")
    await _make_user(pb, "B")
    await _make_management(pa, pb)
    h = await _headers(client, pa)

    res = await client.get("/api/guardian/v13/family/list", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()
    items = data.get("items", [])
    assert len(items) >= 1
    for it in items:
        assert "can_remove" in it
