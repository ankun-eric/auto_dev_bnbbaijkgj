"""[PRD-TA-GUARDIAN-CARD-V1 2026-06-02] 健康档案「守护 TA 的人」卡片改造 - 后端契约测试

覆盖：
1. all-guardians 接口必须返回 max_guardians 字段（新增）
2. max_guardians 默认（无套餐 / 免费）回退为 3
3. 即使没有任何守护人，接口仍返回 200 + items=[] + total=0 + max_guardians=3（被守护人本人调用自己）
4. 多个守护人时 total 与 items 长度一致，且 max_guardians 仍来自被守护人本人的会员套餐
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import FamilyManagement, FamilyMember, User, UserRole


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


async def _make_management(
    manager_phone: str,
    managed_phone: str,
    is_primary: bool = False,
    priority: int = 100,
    delta_seconds: int = 0,
) -> int:
    async with test_session() as s:
        manager = (await s.execute(select(User).where(User.phone == manager_phone))).scalar_one()
        managed = (await s.execute(select(User).where(User.phone == managed_phone))).scalar_one()
        m = FamilyMember(
            user_id=managed.id,
            nickname=managed.nickname or "本人",
            relationship_type="本人",
            is_self=True,
            member_user_id=managed.id,
        )
        s.add(m)
        await s.flush()
        mgmt = FamilyManagement(
            manager_user_id=manager.id,
            managed_user_id=managed.id,
            managed_member_id=m.id,
            status="active",
            is_primary_guardian=is_primary,
            priority_order=priority,
            created_at=datetime.now() + timedelta(seconds=delta_seconds),
        )
        s.add(mgmt)
        await s.flush()
        mid = mgmt.id
        await s.commit()
        return mid


# ─────────── T1: 接口新增 max_guardians 字段 ───────────


@pytest.mark.asyncio
async def test_all_guardians_returns_max_guardians_field(client: AsyncClient):
    """[§6.2] all-guardians 接口必须新增 max_guardians 字段，回退默认值 3"""
    await _make_user("13900100001", "妈妈A")
    await _make_user("13900100002", "女儿A")
    await _make_management("13900100002", "13900100001", is_primary=True, priority=0, delta_seconds=0)

    # 用被守护人（妈妈A）自身视角调用
    headers = await _headers(client, "13900100001")
    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13900100001"))).scalar_one()
        mama_uid = mama.id
    r = await client.get(f"/api/guardian/v12/managed/{mama_uid}/all-guardians", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # 新增字段必须存在
    assert "max_guardians" in data, "返回体必须包含 max_guardians 字段"
    assert isinstance(data["max_guardians"], int)
    assert data["max_guardians"] >= 1, "max_guardians 必须为正整数"
    # 兼容老字段
    assert data["total"] == 1
    assert isinstance(data["items"], list) and len(data["items"]) == 1


# ─────────── T2: 无守护人时也返回 max_guardians 默认值 ───────────


@pytest.mark.asyncio
async def test_all_guardians_no_guardians_returns_max_default(client: AsyncClient):
    """[§4.1 兜底] 即使被守护人没有任何守护人，接口仍返回 max_guardians 默认值 3"""
    await _make_user("13900200001", "孤儿用户")
    headers = await _headers(client, "13900200001")
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == "13900200001"))).scalar_one()
        uid = u.id
    r = await client.get(f"/api/guardian/v12/managed/{uid}/all-guardians", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert "max_guardians" in data
    # 免费会员默认为 3（FreeMemberQuota 缺失时也为 3）
    assert data["max_guardians"] == 3


# ─────────── T3: 多守护人场景下统计与上限独立 ───────────


@pytest.mark.asyncio
async def test_all_guardians_count_and_max_independent(client: AsyncClient):
    """[§4.1] 验证 X(=total) 是被守护人的真实数量，Y(=max_guardians) 是被守护人本人的上限"""
    await _make_user("13900300001", "妈妈B")
    await _make_user("13900300002", "女儿B")
    await _make_user("13900300003", "弟弟B")

    await _make_management("13900300002", "13900300001", is_primary=True, priority=0, delta_seconds=0)
    await _make_management("13900300003", "13900300001", is_primary=False, priority=10, delta_seconds=10)

    # 由女儿（守护人）视角访问
    headers = await _headers(client, "13900300002")
    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13900300001"))).scalar_one()
        mama_uid = mama.id
    r = await client.get(f"/api/guardian/v12/managed/{mama_uid}/all-guardians", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["max_guardians"] == 3  # 妈妈B 默认免费会员，上限 3
    assert data["caller_role"] == "guardian"
    assert data["caller_is_primary"] is True


# ─────────── T4: 调用者权限校验仍然生效 ───────────


@pytest.mark.asyncio
async def test_all_guardians_permission_still_enforced(client: AsyncClient):
    """[§6.2 兼容] 新增 max_guardians 不破坏原有权限：与被守护人无关的第三方仍 403"""
    await _make_user("13900400001", "妈妈C")
    await _make_user("13900400002", "陌生人C")
    await _make_management("13900400001", "13900400001", is_primary=True, priority=0, delta_seconds=0)

    headers = await _headers(client, "13900400002")  # 陌生人
    async with test_session() as s:
        mama = (await s.execute(select(User).where(User.phone == "13900400001"))).scalar_one()
        mama_uid = mama.id
    r = await client.get(f"/api/guardian/v12/managed/{mama_uid}/all-guardians", headers=headers)
    assert r.status_code == 403
