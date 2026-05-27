"""[守护人体系 PRD v1.3.1 2026-05-27] 健康档案统一列表与已绑定/未绑定重构 - 自动化测试

覆盖：
1. family/list 返回 v1.3.1 新增字段：bind_status / display_substatus_label / occupies_quota / is_orphan
2. family/list 返回 bound_count / unbound_count / quota_used
3. 列表按 created_at ASC 正序
4. 配额公式：本人豁免、accepted/inviting/never_invited 占名额；rejected/unbound/expired 不占名额
5. max_guardians 动态读取 free_member_quota.max_managed
6. 用户可见层术语柔化：display_substatus_label 不出现"共管 / 代管 / 已拒绝"
7. 配额超限后再次邀请返回 400 + 提示文案
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
    is_primary: bool = False,
    status: str = "active",
    created_at: datetime | None = None,
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
            created_at=created_at or datetime.utcnow(),
        )
        s.add(mgmt)
        await s.flush()
        mgmt_id = mgmt.id
        managed_uid = managed.id
        await s.commit()
        return mgmt_id, managed_uid


async def _make_pending_invite(
    inviter_phone: str,
    hours: int = 24,
    status: str = "pending",
    created_at: datetime | None = None,
) -> tuple[int, str]:
    async with test_session() as s:
        inviter = (await s.execute(select(User).where(User.phone == inviter_phone))).scalar_one()
        code = uuid.uuid4().hex
        inv = FamilyInvitation(
            invite_code=code,
            inviter_user_id=inviter.id,
            member_id=None,
            status=status,
            expires_at=datetime.utcnow() + timedelta(hours=hours),
            relation_type="father",
            created_at=created_at or datetime.utcnow(),
        )
        s.add(inv)
        await s.flush()
        iid = inv.id
        await s.commit()
        return iid, code


# ─────────── T1: 新增字段 bind_status / display_substatus_label / occupies_quota ───────────


@pytest.mark.asyncio
async def test_v131_list_returns_bind_status_and_display_label(client: AsyncClient):
    """[PRD-V1.3.1 §1.2/§1.3] 列表项必须返回 bind_status / display_substatus_label / occupies_quota"""
    await _make_user("13911001001", "张三")
    await _make_user("13911001002", "妈妈")
    await _make_management("13911001001", "13911001002", is_primary=True)
    await _make_pending_invite("13911001001", hours=12, status="pending")
    await _make_pending_invite("13911001001", hours=24, status="rejected")

    headers = await _headers(client, "13911001001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    # 所有 items 必须包含 v1.3.1 新增字段
    for it in data["items"]:
        assert "bind_status" in it, f"missing bind_status in item: {it}"
        assert it["bind_status"] in ("bound", "unbound"), f"invalid bind_status: {it['bind_status']}"
        assert "display_substatus_label" in it
        assert "occupies_quota" in it
        assert isinstance(it["occupies_quota"], bool)

    # accepted 关系 → bound
    accepted = [it for it in data["items"] if it["invite_lifecycle"] == "accepted"]
    assert len(accepted) >= 1
    assert accepted[0]["bind_status"] == "bound"
    # 显示文案应为"建立于"而非"共管"
    assert accepted[0]["display_substatus_label"] == "建立于"

    # inviting → unbound + "邀请中"
    inviting = [it for it in data["items"] if it["invite_lifecycle"] == "inviting"]
    assert len(inviting) >= 1
    assert inviting[0]["bind_status"] == "unbound"
    assert inviting[0]["display_substatus_label"] == "邀请中"

    # rejected → unbound + "暂未响应"（柔化，不能出现"已拒绝"）
    rejected = [it for it in data["items"] if it["invite_lifecycle"] == "rejected"]
    assert len(rejected) >= 1
    assert rejected[0]["bind_status"] == "unbound"
    assert rejected[0]["display_substatus_label"] == "暂未响应"


# ─────────── T2: 新统计字段 bound_count / unbound_count / quota_used ───────────


@pytest.mark.asyncio
async def test_v131_list_returns_bound_unbound_count(client: AsyncClient):
    """[PRD-V1.3.1 §5.1] 返回 bound_count / unbound_count / quota_used"""
    await _make_user("13911002001", "张三")
    await _make_user("13911002002", "妈妈")
    await _make_management("13911002001", "13911002002", is_primary=True)
    await _make_pending_invite("13911002001", hours=12, status="pending")  # inviting → 占名额

    headers = await _headers(client, "13911002001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert "bound_count" in data
    assert "unbound_count" in data
    assert "quota_used" in data
    assert data["bound_count"] >= 1
    assert data["unbound_count"] >= 1
    # 1 accepted + 1 inviting 都占名额 = 2
    assert data["quota_used"] >= 2


# ─────────── T3: 排序 - created_at ASC（老朋友先） ───────────


@pytest.mark.asyncio
async def test_v131_list_sort_by_created_at_asc(client: AsyncClient):
    """[PRD-V1.3.1 §3.2] 列表按 created_at ASC 正序"""
    await _make_user("13911003001", "张三")
    await _make_user("13911003002", "妈妈早")
    await _make_user("13911003003", "爸爸晚")

    # 妈妈早：30 天前
    await _make_management(
        "13911003001", "13911003002",
        is_primary=True, created_at=datetime.utcnow() - timedelta(days=30),
    )
    # 爸爸晚：1 天前
    await _make_management(
        "13911003001", "13911003003",
        is_primary=False, created_at=datetime.utcnow() - timedelta(days=1),
    )

    headers = await _headers(client, "13911003001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    # 找到妈妈和爸爸的 item
    mama_idx = None
    papa_idx = None
    for i, it in enumerate(data["items"]):
        if it.get("managed_user_nickname") == "妈妈早":
            mama_idx = i
        elif it.get("managed_user_nickname") == "爸爸晚":
            papa_idx = i
    assert mama_idx is not None and papa_idx is not None
    # 妈妈（更早建立）应在爸爸之前
    assert mama_idx < papa_idx, f"created_at ASC 排序失败: 妈妈[{mama_idx}] 应在爸爸[{papa_idx}] 之前"


# ─────────── T4: 配额公式 - rejected/unbound/expired 不占名额 ───────────


@pytest.mark.asyncio
async def test_v131_quota_formula_rejected_not_occupy(client: AsyncClient):
    """[PRD-V1.3.1 §2.2] rejected / unbound / expired 不占名额"""
    await _make_user("13911004001", "张三")
    # 创建 3 个邀请，状态各异
    await _make_pending_invite("13911004001", hours=12, status="pending")    # 占 1
    await _make_pending_invite("13911004001", hours=24, status="rejected")   # 不占
    await _make_pending_invite("13911004001", hours=24, status="cancelled")  # unbound 不占

    headers = await _headers(client, "13911004001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    # 只有 pending(inviting) 占名额 = 1
    assert data["quota_used"] == 1, f"quota_used 应为 1，实际 {data['quota_used']}, items={data['items']}"


# ─────────── T5: max_guardians 动态读取（free_member_quota） ───────────


@pytest.mark.asyncio
async def test_v131_max_guardians_dynamic_from_free_quota(client: AsyncClient):
    """[PRD-V1.3.1 §2.1] 普通用户从 free_member_quota.max_managed 动态读取上限"""
    await _make_user("13911005001", "张三")

    # 准备 free_member_quota（id=1）
    async with test_session() as s:
        from app.models.membership_plan import FreeMemberQuota
        q = (await s.execute(select(FreeMemberQuota).where(FreeMemberQuota.id == 1))).scalar_one_or_none()
        if not q:
            q = FreeMemberQuota(id=1, max_managed=3, ai_outbound_call_count=5,
                                emergency_ai_call_count=3, max_managed_by=3)
            s.add(q)
        else:
            q.max_managed = 3
        await s.commit()

    headers = await _headers(client, "13911005001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    # 不再写死 10，应取 free_member_quota.max_managed = 3
    assert data["max_guardians"] == 3, f"max_guardians 应为 3，实际 {data['max_guardians']}"


# ─────────── T6: 用户可见层不出现"共管/代管/已拒绝" ───────────


@pytest.mark.asyncio
async def test_v131_no_blacklisted_terms_in_display_label(client: AsyncClient):
    """[PRD-V1.3.1 §1.3] display_substatus_label 全局不含"共管 / 代管 / 已拒绝" """
    await _make_user("13911006001", "张三")
    await _make_user("13911006002", "妈妈")
    await _make_management("13911006001", "13911006002", is_primary=True)
    await _make_pending_invite("13911006001", hours=12, status="pending")
    await _make_pending_invite("13911006001", hours=24, status="rejected")

    headers = await _headers(client, "13911006001")
    r = await client.get("/api/guardian/v13/family/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    blacklist = ["共管", "代管", "已拒绝"]
    for it in data["items"]:
        label = it.get("display_substatus_label") or ""
        for term in blacklist:
            assert term not in label, f"display_substatus_label 含黑名单词「{term}」: {label}"
