"""[BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03]
守护我的人 · Bug 修复测试。

覆盖：
- AT-6：已有 1 条 pending 时再创建一条，列表里应有 2 条 pending（旧的不被自动取消）
- AT-7：X 已达上限时再创建，应返回 GUARDIAN_LIMIT_REACHED 错误码
- 数据卫生：已过期的 pending 应被自动标记为 expired
"""
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient

from tests.conftest import test_session
from app.models.models import ReverseGuardianInvitation
from app.models.membership_plan import FreeMemberQuota


async def _register_and_login(client: AsyncClient, phone: str, nickname: str) -> dict:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "pass1234", "nickname": nickname,
    })
    resp = await client.post("/api/auth/login", json={
        "phone": phone, "password": "pass1234",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _get_user_id(headers: dict, client: AsyncClient) -> int:
    resp = await client.get("/api/auth/me", headers=headers)
    return resp.json()["id"]


async def _ensure_free_quota(max_managed_by: int = 3, max_managed: int = 3) -> None:
    """确保有一条 FreeMemberQuota，用于免费用户的 Y 值。"""
    async with test_session() as session:
        from sqlalchemy import select
        existing = await session.execute(select(FreeMemberQuota))
        if existing.scalars().first() is None:
            session.add(FreeMemberQuota(
                max_managed=max_managed,
                max_managed_by=max_managed_by,
            ))
            await session.commit()


@pytest.mark.asyncio
async def test_create_invite_keeps_old_pending(client: AsyncClient):
    """AT-6：再创建一条邀请不应取消之前的 pending。"""
    await _ensure_free_quota(max_managed_by=3)
    headers = await _register_and_login(client, "13811110001", "多pending用户A")

    # 第 1 条
    r1 = await client.post(
        "/api/reverse-guardian/invite",
        headers=headers,
        json={"guardian_name": "张三", "relation_type": "叔叔"},
    )
    assert r1.status_code == 200, r1.text
    code1 = r1.json()["invite_code"]

    # 第 2 条
    r2 = await client.post(
        "/api/reverse-guardian/invite",
        headers=headers,
        json={"guardian_name": "李四", "relation_type": "阿姨"},
    )
    assert r2.status_code == 200, r2.text
    code2 = r2.json()["invite_code"]
    assert code1 != code2

    # 列表应有 2 条 pending
    list_resp = await client.get("/api/reverse-guardian/my-guardians", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    pending_items = [i for i in items if i.get("item_type") == "pending"]
    assert len(pending_items) == 2, f"expect 2 pending, got {len(pending_items)}: {pending_items}"

    # guardian-count 也应反映 X=2
    cnt_resp = await client.get("/api/reverse-guardian/guardian-count", headers=headers)
    cnt = cnt_resp.json()
    assert cnt["pending_count"] == 2
    assert cnt["total_count"] == 2


@pytest.mark.asyncio
async def test_create_invite_limit_reached(client: AsyncClient):
    """AT-7：达到 Y 上限时应返回 GUARDIAN_LIMIT_REACHED。"""
    await _ensure_free_quota(max_managed_by=3)
    headers = await _register_and_login(client, "13811110002", "上限用户B")

    # 创建 3 条 pending
    for i in range(3):
        r = await client.post(
            "/api/reverse-guardian/invite",
            headers=headers,
            json={"guardian_name": f"测试{i}", "relation_type": "其他"},
        )
        assert r.status_code == 200, r.text

    # 第 4 条应被拒
    r4 = await client.post(
        "/api/reverse-guardian/invite",
        headers=headers,
        json={"guardian_name": "超出", "relation_type": "其他"},
    )
    assert r4.status_code == 400
    detail = r4.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("code") == "GUARDIAN_LIMIT_REACHED"
    assert detail.get("x") == 3
    assert detail.get("y") == 3


@pytest.mark.asyncio
async def test_create_invite_marks_expired_pending(client: AsyncClient):
    """数据卫生：创建新邀请时应顺手把已过期的 pending 标记为 expired。"""
    await _ensure_free_quota(max_managed_by=3)
    headers = await _register_and_login(client, "13811110003", "过期清理用户C")
    user_id = await _get_user_id(headers, client)

    # 直接 DB 注入 2 条已过期的 pending
    async with test_session() as session:
        for idx in range(2):
            session.add(ReverseGuardianInvitation(
                invite_code=f"expired_seed_{idx}",
                invitee_user_id=user_id,
                status="pending",
                max_uses=3,
                used_count=0,
                expires_at=datetime.utcnow() - timedelta(hours=1),
            ))
        await session.commit()

    # 创建新邀请
    r = await client.post(
        "/api/reverse-guardian/invite",
        headers=headers,
        json={"guardian_name": "新邀请", "relation_type": "朋友"},
    )
    assert r.status_code == 200, r.text

    # 列表应只有 1 条 pending（过期的不再展示）
    list_resp = await client.get("/api/reverse-guardian/my-guardians", headers=headers)
    items = list_resp.json()["items"]
    pending_items = [i for i in items if i.get("item_type") == "pending"]
    assert len(pending_items) == 1

    # 旧的两条状态应该被改为 expired
    async with test_session() as session:
        from sqlalchemy import select
        res = await session.execute(
            select(ReverseGuardianInvitation).where(
                ReverseGuardianInvitation.invite_code.in_(["expired_seed_0", "expired_seed_1"])
            )
        )
        for inv in res.scalars().all():
            assert inv.status == "expired"


@pytest.mark.asyncio
async def test_create_invite_does_not_cancel_pending(client: AsyncClient):
    """旧 pending 不应被新邀请触发的逻辑改为 cancelled。"""
    await _ensure_free_quota(max_managed_by=3)
    headers = await _register_and_login(client, "13811110004", "保留pending用户D")

    r1 = await client.post(
        "/api/reverse-guardian/invite",
        headers=headers,
        json={"guardian_name": "旧A", "relation_type": "妈妈"},
    )
    assert r1.status_code == 200
    code1 = r1.json()["invite_code"]

    r2 = await client.post(
        "/api/reverse-guardian/invite",
        headers=headers,
        json={"guardian_name": "新B", "relation_type": "爸爸"},
    )
    assert r2.status_code == 200

    # 检查 code1 仍为 pending
    async with test_session() as session:
        from sqlalchemy import select
        res = await session.execute(
            select(ReverseGuardianInvitation).where(
                ReverseGuardianInvitation.invite_code == code1
            )
        )
        inv = res.scalar_one_or_none()
        assert inv is not None
        assert inv.status == "pending", f"expected pending, got {inv.status}"
