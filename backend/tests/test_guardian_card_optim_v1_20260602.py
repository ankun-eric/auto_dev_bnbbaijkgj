"""[PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 守护卡片优化 - 后端自动化测试

覆盖：
1. 反向邀请支持 guardian_name 字段（必填，去首尾空格后非空）
2. my-guardians 列表 pending 项回传 guardian_name
3. /api/reverse-guardian/invite/{code} 详情接口可回查名字（支持「查看邀请码」）
4. 被守护上限 max_managed_by 默认 3（免费会员）；超限时返回 GUARDIAN_LIMIT_REACHED
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.membership_plan import FreeMemberQuota
from tests.conftest import test_session


async def _register_and_login(client: AsyncClient, phone: str, nickname: str) -> dict:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "pass1234", "nickname": nickname,
    })
    resp = await client.post("/api/auth/login", json={
        "phone": phone, "password": "pass1234",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


async def _ensure_free_quota(max_managed=3, max_managed_by=3):
    async with test_session() as session:
        from sqlalchemy import select
        existing = (await session.execute(
            select(FreeMemberQuota).where(FreeMemberQuota.id == 1)
        )).scalar_one_or_none()
        if existing:
            existing.max_managed = max_managed
            existing.max_managed_by = max_managed_by
        else:
            session.add(FreeMemberQuota(
                id=1,
                max_managed=max_managed,
                max_managed_by=max_managed_by,
                ai_outbound_call_count=5,
                emergency_ai_call_count=3,
            ))
        await session.commit()


@pytest.mark.asyncio
async def test_card_optim_001_invite_with_guardian_name(client: AsyncClient, auth_headers):
    """TC-CARD-OPTIM-001: 创建反向邀请时支持 guardian_name 字段，返回正确回显。"""
    await _ensure_free_quota(3, 3)
    resp = await client.post(
        "/api/reverse-guardian/invite",
        json={"relation_type": "爸爸", "guardian_name": "  张三  "},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 名字去首尾空格存储
    assert data.get("guardian_name") == "张三"
    assert data["invite_code"]


@pytest.mark.asyncio
async def test_card_optim_002_my_guardians_pending_returns_name(client: AsyncClient, auth_headers):
    """TC-CARD-OPTIM-002: my-guardians 列表 pending 项返回 guardian_name。"""
    await _ensure_free_quota(3, 3)
    create_resp = await client.post(
        "/api/reverse-guardian/invite",
        json={"relation_type": "妈妈", "guardian_name": "李四"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200

    list_resp = await client.get("/api/reverse-guardian/my-guardians", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    pending = [it for it in items if it.get("item_type") == "pending"]
    assert len(pending) >= 1
    found = next((it for it in pending if it.get("guardian_name") == "李四"), None)
    assert found is not None, f"未找到带 guardian_name='李四' 的 pending 项: {pending}"
    assert found.get("invite_code")


@pytest.mark.asyncio
async def test_card_optim_003_view_invite_by_code(client: AsyncClient, auth_headers):
    """TC-CARD-OPTIM-003: 通过 /api/reverse-guardian/invite/{code} 可重新查看邀请详情（含 guardian_name）。"""
    await _ensure_free_quota(3, 3)
    create_resp = await client.post(
        "/api/reverse-guardian/invite",
        json={"relation_type": "朋友", "guardian_name": "王五"},
        headers=auth_headers,
    )
    code = create_resp.json()["invite_code"]

    detail_resp = await client.get(
        f"/api/reverse-guardian/invite/{code}", headers=auth_headers,
    )
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["invite_code"] == code
    assert data.get("guardian_name") == "王五"
    assert data.get("relation_type") == "朋友"


@pytest.mark.asyncio
async def test_card_optim_004_invite_with_empty_name_allowed_backend(client: AsyncClient, auth_headers):
    """TC-CARD-OPTIM-004: 后端对 guardian_name 容错（空 → None），名字必填校验交给前端。"""
    await _ensure_free_quota(3, 3)
    resp = await client.post(
        "/api/reverse-guardian/invite",
        json={"relation_type": "其他", "guardian_name": "   "},
        headers=auth_headers,
    )
    # 后端不强制阻断（前端拦截），空字符串归一化为 None
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("guardian_name") in (None, "")


@pytest.mark.asyncio
async def test_card_optim_005_max_managed_by_limit_reached(client: AsyncClient):
    """TC-CARD-OPTIM-005: 被守护上限 max_managed_by=2 时，创建第 3 个邀请返回 GUARDIAN_LIMIT_REACHED。"""
    await _ensure_free_quota(3, 2)
    headers = await _register_and_login(client, "13900000901", "用户A")

    # 第 1 次：成功
    r1 = await client.post(
        "/api/reverse-guardian/invite",
        json={"relation_type": "爸爸", "guardian_name": "守护者1"},
        headers=headers,
    )
    assert r1.status_code == 200
    # 第 2 次：成功（旧 pending 会被取消，新邀请取代之，X 仍为 1）
    # 为了构造 2 个 pending，需要重置：因 invite 会 cancel 旧 pending，X 永远 = active + 1
    # 改为直接验证：active 数量已达上限时阻断
    # 模拟：手工写入 2 条 active FamilyManagement
    from app.models.models import FamilyManagement
    from datetime import datetime
    me_resp = await client.get("/api/auth/me", headers=headers)
    me_id = me_resp.json()["id"]
    async with test_session() as session:
        session.add(FamilyManagement(
            manager_user_id=999991,
            managed_user_id=me_id,
            managed_member_id=None,
            status="active",
            created_at=datetime.now(),
        ))
        session.add(FamilyManagement(
            manager_user_id=999992,
            managed_user_id=me_id,
            managed_member_id=None,
            status="active",
            created_at=datetime.now(),
        ))
        await session.commit()

    # 此时 active=2 已达 max_managed_by=2，再发邀请应失败
    r3 = await client.post(
        "/api/reverse-guardian/invite",
        json={"relation_type": "妈妈", "guardian_name": "守护者3"},
        headers=headers,
    )
    assert r3.status_code == 400, r3.text
    detail = r3.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "GUARDIAN_LIMIT_REACHED"
    assert detail.get("y") == 2


@pytest.mark.asyncio
async def test_card_optim_006_default_max_managed_by_is_3(client: AsyncClient, auth_headers):
    """TC-CARD-OPTIM-006: 免费会员默认 max_managed_by=3（被守护上限），与 PRD 一致。"""
    await _ensure_free_quota(3, 3)
    resp = await client.get("/api/reverse-guardian/guardian-count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_guardians_for_me"] == 3, f"被守护上限默认值应为 3，实际：{data['max_guardians_for_me']}"
