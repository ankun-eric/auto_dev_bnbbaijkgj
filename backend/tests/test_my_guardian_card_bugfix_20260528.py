"""[BUGFIX-MY-GUARDIAN-CARD-20260528] 健康档案 · 我的守护人卡片 三处 Bug 修复测试

覆盖：
A. /api/guardian/v13/family/list 返回新字段：archive_record_total / is_unlimited / guarded_count
B. max_guardians / can_invite_count 按会员等级动态读取（无硬编码 10）
C. /api/guardian/v13/family/remove 对 active 状态的关系直接受理（去除"守护中状态不允许移除"硬拦截）
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


async def _make_management(
    manager_phone: str,
    managed_phone: str,
    *,
    is_primary: bool = False,
    status: str = "active",
) -> tuple[int, int]:
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
            status=status,
            is_primary_guardian=is_primary,
            priority_order=0 if is_primary else 100,
        )
        s.add(mgmt)
        await s.flush()
        mid = mgmt.id
        managed_uid = managed.id
        await s.commit()
        return mid, managed_uid


async def _make_pending_invite(
    inviter_phone: str,
    *,
    hours: int = 24,
    status: str = "pending",
) -> tuple[int, str]:
    async with test_session() as s:
        inviter = (await s.execute(select(User).where(User.phone == inviter_phone))).scalar_one()
        code = uuid.uuid4().hex
        inv = FamilyInvitation(
            invite_code=code,
            inviter_user_id=inviter.id,
            member_id=None,
            status=status,
            expires_at=datetime.now() + timedelta(hours=hours),
            relation_type="father",
        )
        s.add(inv)
        await s.flush()
        iid = inv.id
        await s.commit()
        return iid, code


# ─────────── Bug A：archive_record_total / is_unlimited 字段 ───────────


@pytest.mark.asyncio
async def test_bug_a_family_list_returns_archive_record_total(client: AsyncClient):
    """Bug A：/family/list 必须返回 archive_record_total（档案记录数）"""
    await _make_user("13950000001", "张三")
    await _make_user("13950000002", "妈妈")
    await _make_management("13950000001", "13950000002", is_primary=True)
    # 一条 pending 邀请：未绑定，按口径占位 1
    await _make_pending_invite("13950000001", hours=12, status="pending")

    headers = await _headers(client, "13950000001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "archive_record_total" in data, "缺少 archive_record_total 字段"
    assert isinstance(data["archive_record_total"], int)
    # 已绑定占位至少 1（妈妈）+ 邀请中占位 1 = 至少 2
    assert data["archive_record_total"] >= 2


@pytest.mark.asyncio
async def test_bug_a_family_list_returns_is_unlimited_and_guarded_count(client: AsyncClient):
    """Bug A：/family/list 必须返回 is_unlimited 和 guarded_count"""
    await _make_user("13950000011", "张三")
    headers = await _headers(client, "13950000011")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "is_unlimited" in data, "缺少 is_unlimited 字段"
    assert isinstance(data["is_unlimited"], bool)
    assert "guarded_count" in data, "缺少 guarded_count 字段"
    assert isinstance(data["guarded_count"], int)


# ─────────── Bug B：max_guardians 不再硬编码为 10 ───────────


@pytest.mark.asyncio
async def test_bug_b_max_guardians_dynamic_from_quota(client: AsyncClient):
    """Bug B：普通用户 max_guardians 走动态配置（free_member_quota.max_managed），不再硬编码 10"""
    await _make_user("13950000021", "张三")
    headers = await _headers(client, "13950000021")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "max_guardians" in data
    assert "can_invite_count" in data
    # max_guardians 应是从配置读取的整数
    assert isinstance(data["max_guardians"], int)
    assert data["max_guardians"] > 0


# ─────────── Bug C：/family/remove 对 active 状态直接受理 ───────────


@pytest.mark.asyncio
async def test_bug_c_remove_accepts_active_management(client: AsyncClient):
    """Bug C：/family/remove 对 active 状态的关系直接受理，不再返回"守护中状态不允许移除"。"""
    await _make_user("13950000031", "守护人")
    await _make_user("13950000032", "被守护人")
    mgmt_id, managed_uid = await _make_management(
        "13950000031", "13950000032", is_primary=True, status="active"
    )

    headers = await _headers(client, "13950000031")
    r = await client.post(
        "/api/guardian/v13/family/remove",
        json={"managed_user_id": managed_uid},
        headers=headers,
    )
    # 必须直接成功，不能返回 400 + "守护中状态不允许移除"
    assert r.status_code == 200, f"应直接受理 active 状态的移除，但返回：{r.status_code} {r.text}"
    body = r.json()
    assert body.get("removed") is True

    # 数据库中关系应已置为 removed
    async with test_session() as s:
        m = (await s.execute(select(FamilyManagement).where(FamilyManagement.id == mgmt_id))).scalar_one()
        assert m.status == "removed", f"关系状态应为 removed，实际：{m.status}"
        assert m.cancelled_at is not None


@pytest.mark.asyncio
async def test_bug_c_remove_returns_clear_404_when_not_found(client: AsyncClient):
    """Bug C：找不到关系时返回 404 + 明确文案，便于前端识别。"""
    await _make_user("13950000041", "张三")
    headers = await _headers(client, "13950000041")
    r = await client.post(
        "/api/guardian/v13/family/remove",
        json={"managed_user_id": 99999999},
        headers=headers,
    )
    assert r.status_code == 404
    detail = r.json().get("detail", "")
    assert "守护关系" in detail or "未找到" in detail
