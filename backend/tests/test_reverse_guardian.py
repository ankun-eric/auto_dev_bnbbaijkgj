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
