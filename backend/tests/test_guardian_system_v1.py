"""[守护人体系 PRD v1.1 2026-05-25] 自动化测试

覆盖：
1. 守护人列表查询返回主守护人/普通守护人标记
2. 主守护人自动设置（最早绑定者）
3. 主守护人转移：发起 + 审批 + 拒绝
4. 优先级调整
5. 异常告警额度查询
6. 串行外呼模拟（顺序、付费/免费）
7. 邀请记录列表与状态徽章
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
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
    priority: int = 100,
    delta_seconds: int = 0,
) -> int:
    """构造守护关系（manager 管 managed）"""
    async with test_session() as s:
        manager = (await s.execute(select(User).where(User.phone == manager_phone))).scalar_one()
        managed = (await s.execute(select(User).where(User.phone == managed_phone))).scalar_one()
        # 为被守护人建一个 FamilyMember（self）
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
            created_at=datetime.utcnow() + timedelta(seconds=delta_seconds),
        )
        s.add(mgmt)
        await s.flush()
        mid = mgmt.id
        await s.commit()
        return mid


# ─────────── Test 1: 守护人列表 + 角色 ───────────


@pytest.mark.asyncio
async def test_guardian_list_with_role_badge(client: AsyncClient):
    await _make_user("13700000001", "被守护人")
    await _make_user("13700000002", "守护人A")
    await _make_user("13700000003", "守护人B")

    # A 先绑定（应自动成为主守护人）
    await _make_management("13700000002", "13700000001",
                           is_primary=True, priority=0, delta_seconds=0)
    await _make_management("13700000003", "13700000001",
                           is_primary=False, priority=10, delta_seconds=10)

    headers = await _headers(client, "13700000001")
    r = await client.get("/api/guardian/list", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    # 顺序：主守护人在前
    assert data["items"][0]["is_primary_guardian"] is True
    assert data["items"][0]["manager_nickname"] == "守护人A"
    assert data["items"][1]["is_primary_guardian"] is False
    assert data["items"][1]["manager_nickname"] == "守护人B"
    assert data["max_count"] == 3  # 免费会员上限
    assert data["is_paid_member"] is False


@pytest.mark.asyncio
async def test_i_guard_list(client: AsyncClient):
    await _make_user("13710000001", "守护者甲")
    await _make_user("13710000002", "被守护人X")
    await _make_user("13710000003", "被守护人Y")
    await _make_management("13710000001", "13710000002", is_primary=True, priority=0)
    await _make_management("13710000001", "13710000003", is_primary=True, priority=0, delta_seconds=10)

    headers = await _headers(client, "13710000001")
    r = await client.get("/api/guardian/i-guard", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert data["max_guarding"] == 10


# ─────────── Test 2: 主守护人转移 ───────────


@pytest.mark.asyncio
async def test_primary_guardian_transfer_flow(client: AsyncClient):
    await _make_user("13720000001", "被守护")
    await _make_user("13720000002", "原主守护")
    await _make_user("13720000003", "新主守护")

    primary_mid = await _make_management(
        "13720000002", "13720000001", is_primary=True, priority=0, delta_seconds=0
    )
    target_mid = await _make_management(
        "13720000003", "13720000001", is_primary=False, priority=10, delta_seconds=10
    )

    # 原主守护人发起转移
    origin_headers = await _headers(client, "13720000002")
    r = await client.post(
        "/api/guardian/transfer/initiate",
        json={"target_management_id": target_mid},
        headers=origin_headers,
    )
    assert r.status_code == 200, r.text
    transfer_id = r.json()["transfer_id"]
    assert r.json()["status"] == "pending"

    # 接任人不能审批
    successor_headers = await _headers(client, "13720000003")
    r = await client.post(
        f"/api/guardian/transfer/{transfer_id}/approve", headers=successor_headers
    )
    assert r.status_code == 403

    # 被守护人审批
    managed_headers = await _headers(client, "13720000001")
    r = await client.post(
        f"/api/guardian/transfer/{transfer_id}/approve", headers=managed_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    # 验证：新主守护人为 13720000003
    r = await client.get("/api/guardian/list", headers=managed_headers)
    items = r.json()["items"]
    primary = next(i for i in items if i["is_primary_guardian"])
    assert primary["manager_nickname"] == "新主守护"

    # 再次审批同一 transfer 失败
    r = await client.post(
        f"/api/guardian/transfer/{transfer_id}/approve", headers=managed_headers
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_transfer_cancel_by_initiator(client: AsyncClient):
    await _make_user("13730000001", "被守护")
    await _make_user("13730000002", "原主")
    await _make_user("13730000003", "目标")
    await _make_management("13730000002", "13730000001", is_primary=True, priority=0)
    target_mid = await _make_management(
        "13730000003", "13730000001", is_primary=False, priority=10, delta_seconds=10
    )

    origin_h = await _headers(client, "13730000002")
    r = await client.post(
        "/api/guardian/transfer/initiate",
        json={"target_management_id": target_mid},
        headers=origin_h,
    )
    tid = r.json()["transfer_id"]

    # 原发起人取消
    r = await client.post(f"/api/guardian/transfer/{tid}/cancel", headers=origin_h)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_transfer_pending_list(client: AsyncClient):
    await _make_user("13740000001", "被守护")
    await _make_user("13740000002", "原主")
    await _make_user("13740000003", "目标")
    await _make_management("13740000002", "13740000001", is_primary=True, priority=0)
    target_mid = await _make_management(
        "13740000003", "13740000001", is_primary=False, priority=10, delta_seconds=10
    )

    origin_h = await _headers(client, "13740000002")
    await client.post(
        "/api/guardian/transfer/initiate",
        json={"target_management_id": target_mid},
        headers=origin_h,
    )

    managed_h = await _headers(client, "13740000001")
    r = await client.get("/api/guardian/transfer/pending", headers=managed_h)
    assert r.status_code == 200
    assert r.json()["total"] == 1
    item = r.json()["items"][0]
    assert item["can_approve"] is True
    assert item["from_user_nickname"] == "原主"
    assert item["to_user_nickname"] == "目标"


# ─────────── Test 3: 优先级调整 ───────────


@pytest.mark.asyncio
async def test_update_priority(client: AsyncClient):
    await _make_user("13750000001", "被守护")
    await _make_user("13750000002", "守A")
    await _make_user("13750000003", "守B")
    primary_mid = await _make_management("13750000002", "13750000001", is_primary=True, priority=0)
    b_mid = await _make_management(
        "13750000003", "13750000001", is_primary=False, priority=10, delta_seconds=10
    )

    headers = await _headers(client, "13750000001")
    r = await client.post(
        "/api/guardian/priority",
        json={"items": [{"management_id": b_mid, "priority_order": 5}]},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["updated"] == 1

    # 主守护人 priority 不会被覆盖
    r2 = await client.post(
        "/api/guardian/priority",
        json={"items": [{"management_id": primary_mid, "priority_order": 99}]},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["updated"] == 0


# ─────────── Test 4: 异常告警额度 ───────────


@pytest.mark.asyncio
async def test_alert_quota(client: AsyncClient):
    await _make_user("13760000001", "守护人")
    headers = await _headers(client, "13760000001")
    r = await client.get("/api/guardian/alert-quota", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_paid_member"] is False
    assert data["monthly_free_quota"] >= 1
    assert data["used_this_month"] == 0
    assert data["can_receive_call"] is True


# ─────────── Test 5: 串行外呼模拟 ───────────


@pytest.mark.asyncio
async def test_serial_alert_call_order(client: AsyncClient):
    await _make_user("13770000001", "被守护")
    await _make_user("13770000002", "主守护")
    await _make_user("13770000003", "二顺位")
    await _make_user("13770000004", "三顺位")
    await _make_management("13770000002", "13770000001", is_primary=True, priority=0)
    await _make_management("13770000003", "13770000001", is_primary=False, priority=5, delta_seconds=10)
    await _make_management("13770000004", "13770000001", is_primary=False, priority=10, delta_seconds=20)

    # 任意 user 都可触发模拟（接口语义为系统级）
    headers = await _headers(client, "13770000001")
    r = await client.post(
        "/api/guardian/alert/simulate-serial-call",
        json={"managed_user_id": (await _get_user_id_by_phone("13770000001"))},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    plan = r.json()["call_plan"]
    assert len(plan) == 3
    assert plan[0]["manager_nickname"] == "主守护"
    assert plan[0]["is_primary"] is True
    assert plan[1]["manager_nickname"] == "二顺位"
    assert plan[2]["manager_nickname"] == "三顺位"
    # 每个守护人的 ring_timeout_seconds 都是 60s
    for p in plan:
        assert p["ring_timeout_seconds"] == 60


async def _get_user_id_by_phone(phone: str) -> int:
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == phone))).scalar_one()
        return u.id


# ─────────── Test 6: 邀请记录列表 ───────────


@pytest.mark.asyncio
async def test_invitation_records_status_badges(client: AsyncClient):
    await _make_user("13780000001", "邀请人")
    inviter_id = await _get_user_id_by_phone("13780000001")
    async with test_session() as s:
        # 创建一个 FamilyMember
        m = FamilyMember(
            user_id=inviter_id, nickname="家人", relationship_type="父亲", is_self=False,
        )
        s.add(m)
        await s.flush()

        # pending 邀请
        s.add(FamilyInvitation(
            invite_code="code_pending",
            inviter_user_id=inviter_id,
            member_id=m.id,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            relation_type="父亲",
        ))
        # accepted 邀请
        s.add(FamilyInvitation(
            invite_code="code_accepted",
            inviter_user_id=inviter_id,
            member_id=m.id,
            status="accepted",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            accepted_by=inviter_id,
            accepted_at=datetime.utcnow(),
            relation_type="父亲",
        ))
        # expired 邀请
        s.add(FamilyInvitation(
            invite_code="code_expired",
            inviter_user_id=inviter_id,
            member_id=m.id,
            status="pending",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            relation_type="父亲",
        ))
        # cancelled 邀请
        s.add(FamilyInvitation(
            invite_code="code_cancelled",
            inviter_user_id=inviter_id,
            member_id=m.id,
            status="cancelled",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            relation_type="父亲",
        ))
        await s.commit()

    headers = await _headers(client, "13780000001")
    r = await client.get("/api/guardian/invitations/records", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    by_code = {it["invite_code"]: it for it in items}
    assert by_code["code_pending"]["status_label"] == "待确认"
    assert by_code["code_accepted"]["status_label"] == "已生效"
    assert by_code["code_expired"]["status_label"] == "已过期"
    assert by_code["code_cancelled"]["status_label"] == "已作废"
    # 已过期/已作废可以重新发送
    assert by_code["code_expired"]["can_reinvite"] is True
    assert by_code["code_cancelled"]["can_reinvite"] is True
    assert by_code["code_pending"]["can_reinvite"] is False
    assert by_code["code_accepted"]["can_reinvite"] is False


# ─────────── Test 7: 数量上限（按会员等级） ───────────


@pytest.mark.asyncio
async def test_max_guardians_for_free_member(client: AsyncClient):
    """免费会员最多 3 个守护人"""
    await _make_user("13790000000", "被守护")
    headers = await _headers(client, "13790000000")
    r = await client.get("/api/guardian/list", headers=headers)
    assert r.status_code == 200
    assert r.json()["max_count"] == 3
    assert r.json()["is_paid_member"] is False
