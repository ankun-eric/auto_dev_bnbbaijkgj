"""[PRD-FAMILY-V3-EMERGENCY-FIX 2026-06-03 + PRD-FAMILY-V3-STATE-MODEL-V1] 测试

覆盖：
1. 应急修复 SOP：家人 Tab 与健康档案对成员状态(removed / deleted)的过滤口径完全一致
2. V3 状态机：list_family_members 接口返回 v3_main_status / v3_sub_status / v3_can_reinvite /
   v3_show_simplified_view 等 V3 字段
3. derive_v3_state 单元函数:本人 / bound / unbinded / not_applied / applying 等场景
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    User,
)
from app.services.family_member_status import derive_v3_state
from tests.conftest import test_session


# ─────────────── 工具：注册并取 token ───────────────

async def _register(client: AsyncClient, phone: str, nickname: str) -> tuple[int, dict]:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "pwd123456", "nickname": nickname,
    })
    res = await client.post("/api/auth/login", json={"phone": phone, "password": "pwd123456"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == phone))).scalar_one()
        return u.id, headers


# ─────────────── 应急修复 SOP 测试 ───────────────

@pytest.mark.asyncio
async def test_emergency_fix_member_tab_and_archive_consistent_for_removed(client: AsyncClient):
    """6399 复刻:成员 status='removed' 时,家人 Tab 和成员档案两侧都应当无法看到。"""
    uid, headers = await _register(client, "13600000601", "苏群皓")

    async with test_session() as s:
        m = FamilyMember(
            user_id=uid, member_user_id=None, relationship_type="儿子",
            nickname="苏俊林", is_self=False, status="removed",
        )
        s.add(m)
        await s.commit()
        member_id = m.id

    # ① 家人 Tab(/api/family/members) 看不到
    res_tab = await client.get("/api/family/members", headers=headers)
    assert res_tab.status_code == 200
    items = res_tab.json()["items"]
    nicknames = [it["nickname"] for it in items]
    assert "苏俊林" not in nicknames, f"removed 成员不应出现在家人 Tab,实际:{nicknames}"

    # ② /api/health/profile/member/{id} 也应 404
    res_hp = await client.get(f"/api/health/profile/member/{member_id}", headers=headers)
    assert res_hp.status_code == 404, f"removed 成员档案应返回 404,实际:{res_hp.status_code}"


@pytest.mark.asyncio
async def test_emergency_fix_member_tab_and_archive_consistent_for_deleted(client: AsyncClient):
    """status='deleted'(状态机软删) 同样应在两端隐藏。"""
    uid, headers = await _register(client, "13600000602", "测试用户2")

    async with test_session() as s:
        m = FamilyMember(
            user_id=uid, member_user_id=None, relationship_type="父亲",
            nickname="李叔", is_self=False, status="deleted",
        )
        s.add(m)
        await s.commit()
        mid = m.id

    res_tab = await client.get("/api/family/members", headers=headers)
    assert "李叔" not in [it["nickname"] for it in res_tab.json()["items"]]

    res_hp = await client.get(f"/api/health/profile/member/{mid}", headers=headers)
    assert res_hp.status_code == 404


@pytest.mark.asyncio
async def test_emergency_fix_active_member_still_visible_both_sides(client: AsyncClient):
    """正常 active 成员两端都应可见(防止过滤过严误伤)。"""
    uid, headers = await _register(client, "13600000603", "测试用户3")

    async with test_session() as s:
        m = FamilyMember(
            user_id=uid, member_user_id=None, relationship_type="母亲",
            nickname="妈妈", is_self=False, status="active",
        )
        s.add(m)
        await s.commit()
        mid = m.id

    res_tab = await client.get("/api/family/members", headers=headers)
    assert "妈妈" in [it["nickname"] for it in res_tab.json()["items"]]

    res_hp = await client.get(f"/api/health/profile/member/{mid}", headers=headers)
    assert res_hp.status_code == 200


# ─────────────── V3 状态机字段 API 集成 ───────────────

@pytest.mark.asyncio
async def test_v3_fields_present_in_member_list(client: AsyncClient):
    """list_family_members 应返回 V3 主+子状态字段 + 视图开关字段。"""
    uid, headers = await _register(client, "13600000604", "测试V3")
    async with test_session() as s:
        s.add(FamilyMember(
            user_id=uid, member_user_id=None, relationship_type="父亲",
            nickname="老爸", is_self=False, status="active",
        ))
        await s.commit()

    res = await client.get("/api/family/members", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    target = next((it for it in items if it["nickname"] == "老爸"), None)
    assert target is not None
    for k in ("v3_main_status", "v3_sub_status", "v3_can_reinvite",
              "v3_can_edit", "v3_show_simplified_view"):
        assert k in target, f"缺少 V3 字段 {k}"
    assert target["v3_main_status"] in ("unbound", "bound", "deleted")


@pytest.mark.asyncio
async def test_v3_unbinded_view_simplified_after_unbind(client: AsyncClient):
    """解绑成员对应卡片应进入极简视图(show_simplified_view=True) + 可重新邀请。"""
    uid, headers = await _register(client, "13600000605", "解绑测试")
    async with test_session() as s:
        m = FamilyMember(
            user_id=uid, member_user_id=999, relationship_type="儿子",
            nickname="小李", is_self=False, status="active",
        )
        s.add(m)
        await s.flush()
        s.add(FamilyManagement(
            manager_user_id=uid, managed_user_id=999, managed_member_id=m.id,
            status="cancelled",
        ))
        await s.commit()

    res = await client.get("/api/family/members", headers=headers)
    target = next((it for it in res.json()["items"] if it["nickname"] == "小李"), None)
    assert target is not None
    assert target["v3_main_status"] == "unbound"
    assert target["v3_sub_status"] == "unbinded"
    assert target["v3_show_simplified_view"] is True
    assert target["v3_can_reinvite"] is True


# ─────────────── derive_v3_state 单元函数测试 ───────────────

def _mk_member(**kwargs) -> FamilyMember:
    """工厂:补齐 FamilyMember 的 NOT NULL 字段(relationship_type)。"""
    kwargs.setdefault("relationship_type", kwargs.get("nickname", "测试"))
    return FamilyMember(**kwargs)


@pytest.mark.asyncio
async def test_derive_state_self_member():
    async with test_session() as s:
        m = _mk_member(user_id=1, nickname="本人", is_self=True, status="active")
        s.add(m); await s.flush()
        info = await derive_v3_state(s, member=m)
        assert info["main_status"] == "bound"
        assert info["sub_status"] == "bound"
        assert info["show_simplified_view"] is False


@pytest.mark.asyncio
async def test_derive_state_not_applied():
    async with test_session() as s:
        m = _mk_member(user_id=2, nickname="新建未邀请", is_self=False, status="active")
        s.add(m); await s.flush()
        info = await derive_v3_state(s, member=m)
        assert info["main_status"] == "unbound"
        assert info["sub_status"] == "not_applied"
        assert info["can_reinvite"] is True


@pytest.mark.asyncio
async def test_derive_state_applying_within_24h():
    async with test_session() as s:
        m = _mk_member(user_id=3, nickname="邀请中", is_self=False, status="active")
        s.add(m); await s.flush()
        s.add(FamilyInvitation(
            inviter_user_id=3, member_id=m.id, invite_code="TEST001",
            status="pending", expires_at=datetime.utcnow() + timedelta(hours=12),
        ))
        await s.flush()
        info = await derive_v3_state(s, member=m)
        assert info["main_status"] == "unbound"
        assert info["sub_status"] == "applying"
        assert info["can_reinvite"] is False


@pytest.mark.asyncio
async def test_derive_state_invited_expired():
    async with test_session() as s:
        m = _mk_member(user_id=4, nickname="过期", is_self=False, status="active")
        s.add(m); await s.flush()
        s.add(FamilyInvitation(
            inviter_user_id=4, member_id=m.id, invite_code="TEST002",
            status="expired", expires_at=datetime.utcnow() - timedelta(hours=1),
        ))
        await s.flush()
        info = await derive_v3_state(s, member=m)
        assert info["sub_status"] == "invited_expired"
        assert info["can_reinvite"] is True


@pytest.mark.asyncio
async def test_derive_state_self_deleted_for_legacy_status():
    async with test_session() as s:
        m = _mk_member(user_id=5, nickname="已删", is_self=False, status="removed")
        s.add(m); await s.flush()
        info = await derive_v3_state(s, member=m)
        assert info["main_status"] == "deleted"
        assert info["sub_status"] == "self_deleted"
        assert info["show_simplified_view"] is True
        assert info["can_reinvite"] is True
