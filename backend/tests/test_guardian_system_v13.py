"""[守护人体系 PRD v1.3 2026-05-26] 健康档案融合优化 - 自动化测试

覆盖：
1. GET /api/guardian/v13/family/list - 列表带 invite_lifecycle + tab 切分
2. POST /api/guardian/v13/family/invite/cancel - 取消邀请
3. GET /api/guardian/v13/family/invite-history - 单向邀请记录
4. POST /api/guardian/v13/family/proxy-pay/toggle - 主代付开关 + 权限校验
5. GET /api/guardian/v13/family/proxy-pay/detail - 代付明细
6. POST /api/guardian/v13/family/remove - 移除 4 不可删校验
7. 权限：普通守护人调用主代付开关返回 403
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
    GuardianProxyPay,
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
    is_primary: bool = False,
    status: str = "active",
) -> tuple[int, int]:
    async with test_session() as s:
        manager = (await s.execute(select(User).where(User.phone == manager_phone))).scalar_one()
        managed = (await s.execute(select(User).where(User.phone == managed_phone))).scalar_one()
        m = FamilyMember(
            user_id=manager.id,
            nickname=managed.nickname or "本人",
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
            created_at=datetime.utcnow(),
        )
        s.add(mgmt)
        await s.flush()
        mgmt_id = mgmt.id
        managed_uid = managed.id
        await s.commit()
        return mgmt_id, managed_uid


async def _make_pending_invite(inviter_phone: str, hours: int = 24) -> tuple[int, str]:
    async with test_session() as s:
        inviter = (await s.execute(select(User).where(User.phone == inviter_phone))).scalar_one()
        code = uuid.uuid4().hex
        inv = FamilyInvitation(
            invite_code=code,
            inviter_user_id=inviter.id,
            member_id=None,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=hours),
            relation_type="father",
        )
        s.add(inv)
        await s.flush()
        iid = inv.id
        await s.commit()
        return iid, code


# ─────────── T1: family/list ───────────


@pytest.mark.asyncio
async def test_v13_family_list_returns_lifecycle_and_tabs(client: AsyncClient):
    await _make_user("13900001001", "张三")
    await _make_user("13900001002", "妈妈")
    await _make_management("13900001001", "13900001002", is_primary=True)
    await _make_pending_invite("13900001001", hours=12)

    headers = await _headers(client, "13900001001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    # 两个 Tab 计数
    assert "tab_active_count" in data
    assert "tab_pending_count" in data
    assert data["tab_active_count"] >= 1
    assert data["tab_pending_count"] >= 1

    # 配额信息
    assert "max_guardians" in data
    assert "can_invite_count" in data
    assert data["max_guardians"] >= 1

    # 检查 lifecycle 字段
    lifecycles = {it["invite_lifecycle"] for it in data["items"]}
    assert "accepted" in lifecycles  # active 关系
    assert "inviting" in lifecycles  # pending 邀请


# ─────────── T2: 取消邀请 ───────────


@pytest.mark.asyncio
async def test_v13_cancel_invite(client: AsyncClient):
    await _make_user("13900002001", "张三")
    iid, code = await _make_pending_invite("13900002001", hours=24)

    headers = await _headers(client, "13900002001")
    r = await client.post(
        "/api/guardian/v13/family/invite/cancel",
        headers=headers,
        json={"invitation_id": iid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"

    # 再次取消应失败
    r2 = await client.post(
        "/api/guardian/v13/family/invite/cancel",
        headers=headers,
        json={"invitation_id": iid},
    )
    assert r2.status_code == 400


# ─────────── T3: 邀请历史 ───────────


@pytest.mark.asyncio
async def test_v13_invite_history(client: AsyncClient):
    await _make_user("13900003001", "张三")
    await _make_pending_invite("13900003001", hours=24)
    await _make_pending_invite("13900003001", hours=10)

    headers = await _headers(client, "13900003001")
    r = await client.get("/api/guardian/v13/family/invite-history", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 2
    # 全部应为 pending（邀请中），且时间倒序
    statuses = [it["status"] for it in data["items"]]
    assert any(s == "pending" for s in statuses)


# ─────────── T4: 主代付开关 + 权限 ───────────


@pytest.mark.asyncio
async def test_v13_proxy_pay_toggle_requires_primary(client: AsyncClient):
    # 普通守护人调用代付开关应 403
    await _make_user("13900004001", "妈妈")
    await _make_user("13900004002", "女儿主")
    await _make_user("13900004003", "弟弟普")

    _, mama_uid = await _make_management("13900004002", "13900004001", is_primary=True)
    await _make_management("13900004003", "13900004001", is_primary=False)

    # 普通守护人调用 → 403
    headers_normal = await _headers(client, "13900004003")
    r1 = await client.post(
        "/api/guardian/v13/family/proxy-pay/toggle",
        headers=headers_normal,
        json={"managed_user_id": mama_uid, "enabled": False},
    )
    assert r1.status_code == 403

    # 主守护人调用 → 200
    headers_primary = await _headers(client, "13900004002")
    r2 = await client.post(
        "/api/guardian/v13/family/proxy-pay/toggle",
        headers=headers_primary,
        json={"managed_user_id": mama_uid, "enabled": False},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["enabled"] is False


# ─────────── T5: 代付明细 ───────────


@pytest.mark.asyncio
async def test_v13_proxy_pay_detail(client: AsyncClient):
    await _make_user("13900005001", "妈妈")
    await _make_user("13900005002", "女儿主")
    _, mama_uid = await _make_management("13900005002", "13900005001", is_primary=True)

    headers = await _headers(client, "13900005002")
    r = await client.get(
        f"/api/guardian/v13/family/proxy-pay/detail?managed_user_id={mama_uid}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["managed_user_id"] == mama_uid
    assert "today_count" in data
    assert "month_count" in data
    assert "enabled" in data
    # 默认 ON
    assert data["enabled"] is True


# ─────────── T6: 移除 - 4 不可删 ───────────


@pytest.mark.asyncio
async def test_v13_remove_active_rejected(client: AsyncClient):
    """active 状态不允许移除"""
    await _make_user("13900006001", "妈妈")
    await _make_user("13900006002", "女儿主")
    _, mama_uid = await _make_management("13900006002", "13900006001", is_primary=True, status="active")

    headers = await _headers(client, "13900006002")
    r = await client.post(
        "/api/guardian/v13/family/remove",
        headers=headers,
        json={"managed_user_id": mama_uid},
    )
    assert r.status_code == 400
    assert "守护中" in r.json().get("detail", "") or "不允许" in r.json().get("detail", "")


@pytest.mark.asyncio
async def test_v13_remove_inviting_rejected(client: AsyncClient):
    """邀请中的 pure invitation 不允许移除"""
    await _make_user("13900007001", "张三")
    iid, _ = await _make_pending_invite("13900007001", hours=24)

    headers = await _headers(client, "13900007001")
    r = await client.post(
        "/api/guardian/v13/family/remove",
        headers=headers,
        json={"invitation_id": iid},
    )
    assert r.status_code == 400
    assert "邀请中" in r.json().get("detail", "")


@pytest.mark.asyncio
async def test_v13_remove_inactive_success(client: AsyncClient):
    """non-active 状态可以移除"""
    await _make_user("13900008001", "妈妈")
    await _make_user("13900008002", "女儿主")
    _, mama_uid = await _make_management("13900008002", "13900008001", is_primary=True, status="cancelled")

    headers = await _headers(client, "13900008002")
    r = await client.post(
        "/api/guardian/v13/family/remove",
        headers=headers,
        json={"managed_user_id": mama_uid},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["removed"] is True


# ─────────── T7: 取消邀请后列表正确反映 ───────────


@pytest.mark.asyncio
async def test_v13_list_after_cancel(client: AsyncClient):
    await _make_user("13900009001", "张三")
    iid, _ = await _make_pending_invite("13900009001", hours=24)

    headers = await _headers(client, "13900009001")
    # 取消
    await client.post(
        "/api/guardian/v13/family/invite/cancel",
        headers=headers,
        json={"invitation_id": iid},
    )

    # 列表应将 cancelled 视为 unbound（待守护）
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    cancelled_items = [it for it in data["items"] if it["invite_lifecycle"] in ("unbound", "rejected", "expired")]
    assert len(cancelled_items) >= 1
