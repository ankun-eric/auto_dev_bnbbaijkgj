"""反向守护邀请接口测试。

覆盖端点：
- GET  /api/reverse-guardian/guardian-count
- GET  /api/reverse-guardian/my-guardians
- POST /api/reverse-guardian/invite
- GET  /api/reverse-guardian/invite/{invite_code}
- POST /api/reverse-guardian/invite/{invite_code}/accept
- POST /api/reverse-guardian/remove
- GET  /api/devices/my  (member_id 筛选参数)
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient

from tests.conftest import test_session
from app.models.models import (
    FamilyManagement,
    ReverseGuardianInvitation,
    User,
)


async def _register_and_login(client: AsyncClient, phone: str, nickname: str) -> dict:
    """注册并登录，返回 auth headers。"""
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "pass1234", "nickname": nickname,
    })
    resp = await client.post("/api/auth/login", json={
        "phone": phone, "password": "pass1234",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _create_guardian_relation(
    db_session,
    guardian_user_id: int,
    managed_user_id: int,
) -> int:
    """在 DB 直接插入一条 active 守护关系，返回 management_id。"""
    async with test_session() as session:
        mgmt = FamilyManagement(
            manager_user_id=guardian_user_id,
            managed_user_id=managed_user_id,
            status="active",
        )
        session.add(mgmt)
        await session.commit()
        await session.refresh(mgmt)
        return mgmt.id


async def _get_user_id(headers: dict, client: AsyncClient) -> int:
    """通过 /api/auth/me 获取当前用户 id。"""
    resp = await client.get("/api/auth/me", headers=headers)
    return resp.json()["id"]


# ──────────────────────────────────────────────────────────
# guardian-count
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc001_guardian_count_unauthenticated(client: AsyncClient):
    """TC-001: 未认证返回 401。"""
    resp = await client.get("/api/reverse-guardian/guardian-count")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc002_guardian_count_zero(client: AsyncClient, auth_headers):
    """TC-002: 无守护者返回 count=0。"""
    resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_tc003_guardian_count_correct(client: AsyncClient):
    """TC-003: 有守护者时返回正确数量。"""
    managed_h = await _register_and_login(client, "13800010001", "被守护人A")
    guardian_h = await _register_and_login(client, "13800010002", "守护者A")

    managed_id = await _get_user_id(managed_h, client)
    guardian_id = await _get_user_id(guardian_h, client)

    await _create_guardian_relation(None, guardian_id, managed_id)

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=managed_h)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


# ──────────────────────────────────────────────────────────
# my-guardians
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc004_my_guardians_unauthenticated(client: AsyncClient):
    """TC-004: 未认证返回 401。"""
    resp = await client.get("/api/reverse-guardian/my-guardians")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc005_my_guardians_empty(client: AsyncClient, auth_headers):
    """TC-005: 无守护者返回空列表。"""
    resp = await client.get("/api/reverse-guardian/my-guardians", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_tc006_my_guardians_correct_list(client: AsyncClient):
    """TC-006: 有守护者返回正确列表。"""
    managed_h = await _register_and_login(client, "13800020001", "被守护人B")
    guardian_h = await _register_and_login(client, "13800020002", "守护者B")

    managed_id = await _get_user_id(managed_h, client)
    guardian_id = await _get_user_id(guardian_h, client)

    mgmt_id = await _create_guardian_relation(None, guardian_id, managed_id)

    resp = await client.get("/api/reverse-guardian/my-guardians", headers=managed_h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["management_id"] == mgmt_id
    assert item["user_id"] == guardian_id
    assert item["nickname"] == "守护者B"


# ──────────────────────────────────────────────────────────
# invite（生成邀请）
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc007_invite_unauthenticated(client: AsyncClient):
    """TC-007: 未认证返回 401。"""
    resp = await client.post("/api/reverse-guardian/invite")
    assert resp.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_tc008_invite_success(client: AsyncClient, auth_headers):
    """TC-008: 成功生成邀请链接，返回 invite_code 和 qr_url。"""
    resp = await client.post("/api/reverse-guardian/invite", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "invite_code" in data
    assert len(data["invite_code"]) > 0
    assert "qr_url" in data
    assert data["invite_code"] in data["qr_url"]
    assert "expires_at" in data


# ──────────────────────────────────────────────────────────
# invite detail（查看邀请）
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc009_invite_detail_invalid_code(client: AsyncClient, auth_headers):
    """TC-009: 无效 invite_code 返回 404。"""
    resp = await client.get(
        "/api/reverse-guardian/invite/nonexistent_code_xyz",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tc010_invite_detail_valid(client: AsyncClient, auth_headers):
    """TC-010: 有效邀请返回详情。"""
    create_resp = await client.post("/api/reverse-guardian/invite", headers=auth_headers)
    assert create_resp.status_code == 200
    invite_code = create_resp.json()["invite_code"]

    resp = await client.get(
        f"/api/reverse-guardian/invite/{invite_code}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invite_code"] == invite_code
    assert data["status"] == "pending"
    assert data["max_uses"] == 3
    assert data["used_count"] == 0
    assert data["check_result"] == "self_invite"


# ──────────────────────────────────────────────────────────
# accept（接受邀请）
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc011_accept_expired_invite(client: AsyncClient):
    """TC-011: 过期邀请返回错误。"""
    invitee_h = await _register_and_login(client, "13800030001", "过期邀请人")
    guardian_h = await _register_and_login(client, "13800030002", "接受者A")

    invitee_id = await _get_user_id(invitee_h, client)

    async with test_session() as session:
        inv = ReverseGuardianInvitation(
            invite_code="expired_test_code_001",
            invitee_user_id=invitee_id,
            status="pending",
            max_uses=3,
            used_count=0,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        session.add(inv)
        await session.commit()

    resp = await client.post(
        "/api/reverse-guardian/invite/expired_test_code_001/accept",
        headers=guardian_h,
    )
    assert resp.status_code == 400
    assert "过期" in resp.text or "失效" in resp.text


@pytest.mark.asyncio
async def test_tc012_accept_self_invite_rejected(client: AsyncClient):
    """TC-012: 自己不能守护自己。"""
    user_h = await _register_and_login(client, "13800040001", "自己守护自己")

    create_resp = await client.post("/api/reverse-guardian/invite", headers=user_h)
    assert create_resp.status_code == 200
    invite_code = create_resp.json()["invite_code"]

    resp = await client.post(
        f"/api/reverse-guardian/invite/{invite_code}/accept",
        headers=user_h,
    )
    assert resp.status_code == 400
    assert "自己" in resp.text


@pytest.mark.asyncio
async def test_tc013_accept_invite_success(client: AsyncClient):
    """TC-013: 成功接受邀请。"""
    invitee_h = await _register_and_login(client, "13800050001", "被守护C")
    guardian_h = await _register_and_login(client, "13800050002", "守护者C")

    create_resp = await client.post("/api/reverse-guardian/invite", headers=invitee_h)
    assert create_resp.status_code == 200
    invite_code = create_resp.json()["invite_code"]

    resp = await client.post(
        f"/api/reverse-guardian/invite/{invite_code}/accept",
        headers=guardian_h,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "management_id" in data
    assert data["management_id"] > 0

    count_resp = await client.get("/api/reverse-guardian/guardian-count", headers=invitee_h)
    assert count_resp.json()["count"] == 1


# ──────────────────────────────────────────────────────────
# remove（解除守护）
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc014_remove_unauthenticated(client: AsyncClient):
    """TC-014: 未认证返回 401。"""
    resp = await client.post(
        "/api/reverse-guardian/remove",
        json={"management_id": 1},
    )
    assert resp.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_tc015_remove_guardian_success(client: AsyncClient):
    """TC-015: 成功解除守护关系。"""
    managed_h = await _register_and_login(client, "13800060001", "被守护D")
    guardian_h = await _register_and_login(client, "13800060002", "守护者D")

    managed_id = await _get_user_id(managed_h, client)
    guardian_id = await _get_user_id(guardian_h, client)

    mgmt_id = await _create_guardian_relation(None, guardian_id, managed_id)

    resp = await client.post(
        "/api/reverse-guardian/remove",
        headers=managed_h,
        json={"management_id": mgmt_id},
    )
    assert resp.status_code == 200
    assert "解除" in resp.json()["message"]

    count_resp = await client.get("/api/reverse-guardian/guardian-count", headers=managed_h)
    assert count_resp.json()["count"] == 0


# ──────────────────────────────────────────────────────────
# devices member filter
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc016_devices_member_id_zero_returns_all(client: AsyncClient, auth_headers):
    """TC-016: member_id=0 返回全部设备（等同于不传 member_id）。"""
    resp_default = await client.get("/api/devices/my", headers=auth_headers)
    resp_zero = await client.get("/api/devices/my?member_id=0", headers=auth_headers)
    assert resp_default.status_code == 200
    assert resp_zero.status_code == 200
    assert resp_default.json()["total"] == resp_zero.json()["total"]


@pytest.mark.asyncio
async def test_tc017_devices_member_id_nonexist_returns_empty(client: AsyncClient, auth_headers):
    """TC-017: member_id=999 返回空列表（无绑定设备的成员）。"""
    resp = await client.get("/api/devices/my?member_id=999", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


# ──────────────────────────────────────────────────────────
# [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527]
# guardian-count 双数字（active_count / pending_count / total_count）
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc018_guardian_count_dual_fields_zero(client: AsyncClient, auth_headers):
    """TC-018: 无任何守护关系和邀请时，新增字段均为 0。"""
    resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data.get("active_count") == 0
    assert data.get("pending_count") == 0
    assert data.get("total_count") == 0


@pytest.mark.asyncio
async def test_tc019_guardian_count_with_pending_invite(client: AsyncClient):
    """TC-019: 有未使用且未过期的反向邀请，pending_count=1。"""
    user_h = await _register_and_login(client, "13800070001", "双数字测试用户")
    user_id = await _get_user_id(user_h, client)

    async with test_session() as session:
        inv = ReverseGuardianInvitation(
            invite_code="dual_count_pending_001",
            invitee_user_id=user_id,
            status="pending",
            max_uses=3,
            used_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        session.add(inv)
        await session.commit()

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=user_h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0  # 兼容字段=active_count
    assert data["active_count"] == 0
    assert data["pending_count"] == 1
    assert data["total_count"] == 1


@pytest.mark.asyncio
async def test_tc020_guardian_count_expired_invite_not_counted(client: AsyncClient):
    """TC-020: 已过期邀请不计入 pending_count。"""
    user_h = await _register_and_login(client, "13800070002", "过期邀请测试")
    user_id = await _get_user_id(user_h, client)

    async with test_session() as session:
        inv = ReverseGuardianInvitation(
            invite_code="dual_count_expired_001",
            invitee_user_id=user_id,
            status="pending",
            max_uses=3,
            used_count=0,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        session.add(inv)
        await session.commit()

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=user_h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_count"] == 0
    assert data["total_count"] == 0


@pytest.mark.asyncio
async def test_tc021_guardian_count_used_up_invite_not_counted(client: AsyncClient):
    """TC-021: 已用完（used_count >= max_uses）的邀请不计入 pending_count。"""
    user_h = await _register_and_login(client, "13800070003", "用完邀请测试")
    user_id = await _get_user_id(user_h, client)

    async with test_session() as session:
        inv = ReverseGuardianInvitation(
            invite_code="dual_count_used_up_001",
            invitee_user_id=user_id,
            status="pending",
            max_uses=3,
            used_count=3,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        session.add(inv)
        await session.commit()

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=user_h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_count"] == 0


@pytest.mark.asyncio
async def test_tc022_guardian_count_active_plus_pending(client: AsyncClient):
    """TC-022: 同时有 active 守护关系和 pending 邀请，total_count=active+pending。"""
    managed_h = await _register_and_login(client, "13800080001", "总数测试-被守护")
    guardian_h = await _register_and_login(client, "13800080002", "总数测试-守护者")

    managed_id = await _get_user_id(managed_h, client)
    guardian_id = await _get_user_id(guardian_h, client)

    await _create_guardian_relation(None, guardian_id, managed_id)

    async with test_session() as session:
        inv = ReverseGuardianInvitation(
            invite_code="dual_count_combo_001",
            invitee_user_id=managed_id,
            status="pending",
            max_uses=3,
            used_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        session.add(inv)
        await session.commit()

    resp = await client.get("/api/reverse-guardian/guardian-count", headers=managed_h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_count"] == 1
    assert data["pending_count"] == 1
    assert data["total_count"] == 2
    assert data["count"] == 1  # 兼容字段始终等于 active_count


# ──────────────────────────────────────────────────────────
# [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527]
# /api/guardian/v12/i-guard 列表包含本人虚拟项
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc023_i_guard_includes_self_when_no_managed(client: AsyncClient, auth_headers):
    """TC-023: 无守护人时，i-guard 仍返回 1 条（本人），total_count=1。"""
    resp = await client.get("/api/guardian/v12/i-guard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    assert data["active_count"] >= 1
    assert len(data["items"]) >= 1
    first = data["items"][0]
    assert first.get("is_self") is True
    assert first.get("relation_label") == "本人"
    assert first.get("role_badge") == "self"


@pytest.mark.asyncio
async def test_tc024_i_guard_self_plus_managed(client: AsyncClient):
    """TC-024: 我守护了 1 个人时，total_count=2（本人 + 1 个被守护人），本人置顶。"""
    me_h = await _register_and_login(client, "13800090001", "我守护测试")
    other_h = await _register_and_login(client, "13800090002", "被我守护的人")

    me_id = await _get_user_id(me_h, client)
    other_id = await _get_user_id(other_h, client)

    await _create_guardian_relation(None, me_id, other_id)

    resp = await client.get("/api/guardian/v12/i-guard", headers=me_h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 2
    assert data["active_count"] == 2
    assert data["items"][0].get("is_self") is True  # 本人置顶
    # 第二项应是真实被守护人
    assert data["items"][1].get("is_self") in (False, None)
    assert data["items"][1]["managed_user_id"] == other_id
