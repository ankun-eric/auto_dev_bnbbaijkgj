"""[PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] ai-home 主页空闲超时归档 & 历史会话列表优化

覆盖范围：
- 列表接口 status 过滤：默认 archived；status=active / all 可选
- 创建接口：默认 status=active；同时归档旧 active
- 归档接口：真正改 status=archived，写入 archived_at
- 新增 /active 接口：返回当前活跃会话；不存在返回 null
- 新增 /resume 接口：archived→active 同时把旧 active 归档
- last_active_at 字段在响应中正确返回
- 切咨询对象：archive_previous_session_id 真正改 status
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    ChatSession,
    FamilyMember,
    SessionType,
    User,
)


# ─────────────────── 共用工具 ───────────────────


async def _register_and_login(client: AsyncClient, phone: str):
    reg = await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "user123", "nickname": f"用户{phone[-4:]}"},
    )
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user"]["id"]
    login = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": "user123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def _seed_session(
    db_session,
    user_id: int,
    *,
    status: str = "archived",
    title: str = "测试对话",
    family_member_id: int | None = None,
    message_count: int = 1,
    last_active_at: datetime | None = None,
    archived_at: datetime | None = None,
) -> ChatSession:
    s = ChatSession(
        user_id=user_id,
        session_type=SessionType.health_qa,
        title=title,
        family_member_id=family_member_id,
        message_count=message_count,
        is_pinned=False,
        is_deleted=False,
        status=status,
        last_active_at=last_active_at or datetime.now(),
        archived_at=archived_at,
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


# ─────────────────── 1. 列表接口 status 过滤 ───────────────────


@pytest.mark.asyncio
async def test_idle_archive_v1_list_default_only_archived(client: AsyncClient, db_session):
    """默认列表仅返回 archived；active 不出现。"""
    user_id, headers = await _register_and_login(client, "13900050001")
    s_arch = await _seed_session(db_session, user_id, status="archived", title="历史会话")
    s_act = await _seed_session(db_session, user_id, status="active", title="活跃会话")

    resp = await client.get("/api/chat-sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    ids = [it["id"] for it in resp.json()]
    assert s_arch.id in ids
    assert s_act.id not in ids


@pytest.mark.asyncio
async def test_idle_archive_v1_list_status_active(client: AsyncClient, db_session):
    """status=active 时仅返回 active；archived 不出现。"""
    user_id, headers = await _register_and_login(client, "13900050002")
    s_arch = await _seed_session(db_session, user_id, status="archived", title="历史")
    s_act = await _seed_session(db_session, user_id, status="active", title="当前")

    resp = await client.get("/api/chat-sessions?status=active", headers=headers)
    assert resp.status_code == 200
    ids = [it["id"] for it in resp.json()]
    assert s_act.id in ids
    assert s_arch.id not in ids


@pytest.mark.asyncio
async def test_idle_archive_v1_list_status_all(client: AsyncClient, db_session):
    """status=all 时同时返回 archived + active。"""
    user_id, headers = await _register_and_login(client, "13900050003")
    s_arch = await _seed_session(db_session, user_id, status="archived", title="A1")
    s_act = await _seed_session(db_session, user_id, status="active", title="A2")

    resp = await client.get("/api/chat-sessions?status=all", headers=headers)
    assert resp.status_code == 200
    ids = [it["id"] for it in resp.json()]
    assert s_arch.id in ids
    assert s_act.id in ids


@pytest.mark.asyncio
async def test_idle_archive_v1_list_returns_status_fields(client: AsyncClient, db_session):
    """列表项返回 status / archived_at / last_active_at 三个新字段。"""
    user_id, headers = await _register_and_login(client, "13900050004")
    arch_at = datetime.now() - timedelta(hours=2)
    last_at = datetime.now() - timedelta(hours=3)
    s = await _seed_session(
        db_session, user_id, status="archived",
        title="带状态字段", last_active_at=last_at, archived_at=arch_at,
    )

    resp = await client.get("/api/chat-sessions", headers=headers)
    assert resp.status_code == 200
    item = next((it for it in resp.json() if it["id"] == s.id), None)
    assert item is not None
    assert item["status"] == "archived"
    assert item["archived_at"] is not None
    assert item["last_active_at"] is not None


# ─────────────────── 2. POST 创建：默认 active + 自动归档旧 active ───────────────────


@pytest.mark.asyncio
async def test_idle_archive_v1_create_defaults_to_active(client: AsyncClient, db_session):
    """新创建会话状态为 active，last_active_at 非空。"""
    user_id, headers = await _register_and_login(client, "13900050010")
    resp = await client.post(
        "/api/chat-sessions",
        json={"session_type": "health_qa", "title": "新对话"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "active"
    assert data["last_active_at"] is not None


@pytest.mark.asyncio
async def test_idle_archive_v1_create_auto_archives_old_active(client: AsyncClient, db_session):
    """创建新 active 时，旧 active 被自动归档（保证全局唯一 active）。"""
    user_id, headers = await _register_and_login(client, "13900050011")
    # 先 seed 一个 active
    old_active = await _seed_session(db_session, user_id, status="active", title="旧 active")

    # 创建新会话 → 应触发自动归档
    resp = await client.post(
        "/api/chat-sessions",
        json={"session_type": "health_qa", "title": "新 active"},
        headers=headers,
    )
    assert resp.status_code == 200
    new_data = resp.json()
    assert new_data["status"] == "active"
    assert old_active.id in (new_data.get("archived_old_ids") or [])

    # 直接查 DB 校验旧 active 已变为 archived
    await db_session.commit()
    await db_session.refresh(old_active)
    assert old_active.status == "archived"
    assert old_active.archived_at is not None


@pytest.mark.asyncio
async def test_idle_archive_v1_create_archive_previous_session_id(client: AsyncClient, db_session):
    """archive_previous_session_id 携带时显式归档旧会话。"""
    user_id, headers = await _register_and_login(client, "13900050012")
    prev = await _seed_session(db_session, user_id, status="active", title="prev")

    resp = await client.post(
        "/api/chat-sessions",
        json={"session_type": "health_qa", "title": "next", "archive_previous_session_id": prev.id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert prev.id in (data.get("archived_old_ids") or [])

    await db_session.commit()
    await db_session.refresh(prev)
    assert prev.status == "archived"


# ─────────────────── 3. 归档接口真正改 status ───────────────────


@pytest.mark.asyncio
async def test_idle_archive_v1_archive_endpoint_changes_status(client: AsyncClient, db_session):
    """POST /api/chat-sessions/{id}/archive 必须把 status 改为 archived 并写入 archived_at。"""
    user_id, headers = await _register_and_login(client, "13900050020")
    s = await _seed_session(db_session, user_id, status="active", title="即将归档")

    resp = await client.post(f"/api/chat-sessions/{s.id}/archive", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "archived"
    assert data["archived_at"] is not None

    await db_session.commit()
    await db_session.refresh(s)
    assert s.status == "archived"
    assert s.archived_at is not None


# ─────────────────── 4. GET /active 接口 ───────────────────


@pytest.mark.asyncio
async def test_idle_archive_v1_active_endpoint_returns_active(client: AsyncClient, db_session):
    """有 active 时返回；无 active 时返回 None。"""
    user_id, headers = await _register_and_login(client, "13900050030")

    # 无 active
    resp = await client.get("/api/chat-sessions/active", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["session"] is None

    # 有 active
    s = await _seed_session(db_session, user_id, status="active", title="active")
    resp2 = await client.get("/api/chat-sessions/active", headers=headers)
    assert resp2.status_code == 200
    data = resp2.json()["session"]
    assert data is not None
    assert data["id"] == s.id
    assert data["status"] == "active"


# ─────────────────── 5. POST /resume 接口 ───────────────────


@pytest.mark.asyncio
async def test_idle_archive_v1_resume_endpoint(client: AsyncClient, db_session):
    """resume：把指定 archived → active，同时把旧 active 归档。"""
    user_id, headers = await _register_and_login(client, "13900050040")
    old_active = await _seed_session(db_session, user_id, status="active", title="当前活跃")
    archived = await _seed_session(db_session, user_id, status="archived", title="历史会话")

    resp = await client.post(f"/api/chat-sessions/{archived.id}/resume", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["session"]["id"] == archived.id
    assert data["session"]["status"] == "active"
    assert old_active.id in data["archived_old_ids"]

    await db_session.commit()
    await db_session.refresh(archived)
    await db_session.refresh(old_active)
    assert archived.status == "active"
    assert old_active.status == "archived"


@pytest.mark.asyncio
async def test_idle_archive_v1_resume_404_if_not_owner(client: AsyncClient, db_session):
    """resume 越权访问返回 404。"""
    user_a_id, headers_a = await _register_and_login(client, "13900050041")
    user_b_id, _ = await _register_and_login(client, "13900050042")
    b_session = await _seed_session(db_session, user_b_id, status="archived", title="B的会话")

    resp = await client.post(f"/api/chat-sessions/{b_session.id}/resume", headers=headers_a)
    assert resp.status_code == 404
