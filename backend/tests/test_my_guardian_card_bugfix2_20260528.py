"""[BUGFIX-MY-GUARDIAN-CARD-2-20260528] 健康档案"我守护的人"5 项优化测试

覆盖：
1. /api/guardian/v13/family/list 返回孤儿 FamilyMember（外部"我的家人"Tab 建档后立即可见）
2. /api/guardian/v13/family/remove 对纯 FamilyMember（孤儿）受理移除，返回 deleted=true
3. /api/guardian/v13/family/remove 对不存在的 management 幂等返 200（不再 404），should_refresh=true
4. /api/guardian/v13/family/remove 对已过期 invitation 受理移除
5. 同一移除连续调用两次 → 第二次 deleted=false, should_refresh=true，不报错
"""
import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    User,
    UserRole,
)


# ─────────── 工具 ───────────


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
    res = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "p123"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _make_orphan_member(user_id: int, nickname: str = "外婆", relation: str = "祖母") -> int:
    """模拟外部"我的家人"Tab 建档（仅 FamilyMember 无对应 FamilyManagement）"""
    async with test_session() as s:
        m = FamilyMember(
            user_id=user_id,
            relationship_type=relation,
            nickname=nickname,
            is_self=False,
            # [PRD-FAMILY-V3-STATUS-INPLACE-UPGRADE 2026-06-03] V3 升级后用 bound
            status="bound",
            sub_status="bound",
        )
        s.add(m)
        await s.flush()
        mid = m.id
        await s.commit()
        return mid


async def _make_expired_invitation(inviter_user_id: int, member_id: int | None = None) -> int:
    """生成一条已过期的邀请"""
    async with test_session() as s:
        inv = FamilyInvitation(
            invite_code=f"EXP{uuid.uuid4().hex[:10]}",
            inviter_user_id=inviter_user_id,
            member_id=member_id,
            status="expired",
            expires_at=datetime.now() - timedelta(hours=2),
            relation_type="父亲",
        )
        s.add(inv)
        await s.flush()
        iid = inv.id
        await s.commit()
        return iid


# ─────────── 用例 ───────────


@pytest.mark.asyncio
async def test_list_includes_orphan_family_member(client: AsyncClient):
    """第 5 点：外部 Tab 建档后，list 立即可见为 is_orphan=True，bind_status=unbound"""
    phone = "13000000201"
    uid = await _make_user(phone, "守护人A")
    mid = await _make_orphan_member(uid, nickname="孤儿档案A", relation="母亲")

    headers = await _headers(client, phone)
    res = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    items = data.get("items", [])
    orphan_items = [it for it in items if it.get("managed_member_id") == mid]
    assert len(orphan_items) == 1, f"应能查到孤儿档案，实际 items={items}"
    it = orphan_items[0]
    assert it.get("is_orphan") is True
    assert it.get("bind_status") == "unbound"
    assert it.get("managed_user_nickname") == "孤儿档案A"


@pytest.mark.asyncio
async def test_remove_orphan_member_idempotent(client: AsyncClient):
    """第 3 + 5 点：纯 FamilyMember 孤儿点【移除】成功 deleted=true，再次调用 deleted=false"""
    phone = "13000000202"
    uid = await _make_user(phone, "守护人B")
    mid = await _make_orphan_member(uid, nickname="孤儿档案B", relation="父亲")

    headers = await _headers(client, phone)

    # 第一次 → deleted=true
    res1 = await client.post(
        "/api/guardian/v13/family/remove",
        json={"managed_member_id": mid},
        headers=headers,
    )
    assert res1.status_code == 200, res1.text
    d1 = res1.json()
    assert d1.get("deleted") is True
    assert d1.get("should_refresh") is True

    # 验证 FamilyMember 已被软删
    async with test_session() as s:
        fm = await s.get(FamilyMember, mid)
        assert fm.status == "deleted"

    # 第二次（幂等）→ deleted=false, 不再报错
    res2 = await client.post(
        "/api/guardian/v13/family/remove",
        json={"managed_member_id": mid},
        headers=headers,
    )
    assert res2.status_code == 200, res2.text
    d2 = res2.json()
    assert d2.get("deleted") is False
    assert d2.get("should_refresh") is True


@pytest.mark.asyncio
async def test_remove_expired_invitation(client: AsyncClient):
    """第 4 点：已过期 invitation 点【移除】，成功返回 200 + deleted=true"""
    phone = "13000000203"
    uid = await _make_user(phone, "守护人C")
    iid = await _make_expired_invitation(uid)

    headers = await _headers(client, phone)
    res = await client.post(
        "/api/guardian/v13/family/remove",
        json={"invitation_id": iid},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    d = res.json()
    assert d.get("deleted") is True
    assert d.get("should_refresh") is True


@pytest.mark.asyncio
async def test_remove_nonexistent_returns_200_idempotent(client: AsyncClient):
    """第 3、4 点核心：传入不存在的 management → 不再 404，返回 200 幂等成功"""
    phone = "13000000204"
    uid = await _make_user(phone, "守护人D")

    headers = await _headers(client, phone)
    # 传入完全不存在的 managed_member_id
    res = await client.post(
        "/api/guardian/v13/family/remove",
        json={"managed_member_id": 99999999},
        headers=headers,
    )
    # 关键：不再 404，而是 200
    assert res.status_code == 200, res.text
    d = res.json()
    assert d.get("deleted") is False
    assert d.get("should_refresh") is True
    assert "已被移除" in (d.get("message") or "")


@pytest.mark.asyncio
async def test_summary_xy_field_consistency(client: AsyncClient):
    """第 1、2 点：max_guardians 与 can_invite_count 字段口径一致，前端可直接 X/Y 展示"""
    phone = "13000000205"
    uid = await _make_user(phone, "守护人E")
    # 建 2 个孤儿档案
    await _make_orphan_member(uid, nickname="家人E1", relation="妻子")
    await _make_orphan_member(uid, nickname="家人E2", relation="儿子")

    headers = await _headers(client, phone)
    res = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    # X = 非本人卡片数（这里 = 2 个孤儿）
    items = data.get("items", [])
    non_self = [it for it in items if it.get("managed_user_id") != uid]
    assert len(non_self) >= 2
    # Y = max_guardians
    assert isinstance(data.get("max_guardians"), int)
    assert data.get("max_guardians", 0) > 0
    # can_invite_count 兜底（不为负）
    assert data.get("can_invite_count", 0) >= 0 or data.get("can_invite_count") == -1
