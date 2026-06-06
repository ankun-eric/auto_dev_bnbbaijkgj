"""[PRD-425 2026-05-08] AI 对话首页顶栏未读数徽标——统一未读总数接口测试。

覆盖：
- T01：未登录访问 → 401
- T02：登录用户、无任何未读 → unreadCount = 0
- T03：仅 SystemMessage 有未读 → 累加
- T04：仅 Notification 有未读 → 累加
- T05：SystemMessage + Notification 都有未读 → 总数累加
- T06：已读消息不计入未读
- T07：兜底场景：返回的响应结构符合 PRD §6.2.1
"""
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import async_session as async_session_maker
from app.models.models import (
    Notification,
    NotificationType,
    SystemMessage,
    User,
)


# ─────────── T01 未登录 401 ───────────


@pytest.mark.asyncio
async def test_t01_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/notifications/unread-count")
    assert resp.status_code in (401, 403), resp.text


# ─────────── T02 登录用户无未读 ───────────


@pytest.mark.asyncio
async def test_t02_no_unread(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["unreadCount"] == 0
    assert body["data"]["breakdown"]["system_messages"] == 0
    assert body["data"]["breakdown"]["notifications"] == 0


# ─────────── 工具：获取用户 id ───────────


async def _get_test_user_id() -> int:
    async with async_session_maker() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        user = res.scalar_one_or_none()
        return user.id if user else 0


# ─────────── T03 仅 SystemMessage 有未读 ───────────


@pytest.mark.asyncio
async def test_t03_system_message_unread(client: AsyncClient, auth_headers):
    user_id = await _get_test_user_id()
    assert user_id > 0
    async with async_session_maker() as session:
        for i in range(3):
            session.add(
                SystemMessage(
                    message_type="system",
                    recipient_user_id=user_id,
                    title=f"测试系统消息 {i}",
                    content="测试内容",
                    is_read=False,
                )
            )
        await session.commit()

    resp = await client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["unreadCount"] == 3
    assert data["breakdown"]["system_messages"] == 3
    assert data["breakdown"]["notifications"] == 0


# ─────────── T04 仅 Notification 有未读 ───────────


@pytest.mark.asyncio
async def test_t04_notification_unread(client: AsyncClient, auth_headers):
    user_id = await _get_test_user_id()
    async with async_session_maker() as session:
        # 清理 SystemMessage 的未读
        from sqlalchemy import update as sa_update
        await session.execute(
            sa_update(SystemMessage)
            .where(SystemMessage.recipient_user_id == user_id, SystemMessage.is_read == False)
            .values(is_read=True, read_at=datetime.now())
        )
        for i in range(2):
            session.add(
                Notification(
                    user_id=user_id,
                    title=f"测试业务通知 {i}",
                    content="测试内容",
                    type=NotificationType.system,
                    is_read=False,
                )
            )
        await session.commit()

    resp = await client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["unreadCount"] == 2
    assert data["breakdown"]["system_messages"] == 0
    assert data["breakdown"]["notifications"] == 2


# ─────────── T05 两类都有 ───────────


@pytest.mark.asyncio
async def test_t05_combined(client: AsyncClient, auth_headers):
    user_id = await _get_test_user_id()
    async with async_session_maker() as session:
        session.add(
            SystemMessage(
                message_type="announcement",
                recipient_user_id=user_id,
                title="公告 X",
                content="...",
                is_read=False,
            )
        )
        await session.commit()

    resp = await client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # T04 已经留了 2 条 Notification 未读 + T05 新增 1 条 SystemMessage = 3
    assert data["breakdown"]["system_messages"] == 1
    assert data["breakdown"]["notifications"] == 2
    assert data["unreadCount"] == 3


# ─────────── T06 已读不计入 ───────────


@pytest.mark.asyncio
async def test_t06_read_not_counted(client: AsyncClient, auth_headers):
    user_id = await _get_test_user_id()
    async with async_session_maker() as session:
        from sqlalchemy import update as sa_update
        # 把 T05 留下的所有未读都标为已读
        await session.execute(
            sa_update(SystemMessage)
            .where(SystemMessage.recipient_user_id == user_id, SystemMessage.is_read == False)
            .values(is_read=True, read_at=datetime.now())
        )
        await session.execute(
            sa_update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True, read_at=datetime.now())
        )
        await session.commit()

    resp = await client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["unreadCount"] == 0


# ─────────── T07 响应结构对齐 PRD §6.2.1 ───────────


@pytest.mark.asyncio
async def test_t07_response_schema(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) >= {"code", "msg", "data"}
    assert body["code"] == 0
    assert "unreadCount" in body["data"]
    assert isinstance(body["data"]["unreadCount"], int)
