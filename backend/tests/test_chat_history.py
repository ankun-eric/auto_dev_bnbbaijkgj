import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import (
    ChatMessage,
    ChatSession,
    MessageRole,
    MessageType,
    SessionType,
    User,
    UserRole,
)

from .conftest import test_session


async def _create_admin(db_session, phone="13800100001") -> User:
    user = User(
        phone=phone,
        password_hash=get_password_hash("admin123"),
        nickname="管理员",
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _admin_headers(client: AsyncClient, phone="13800100001", password="admin123"):
    resp = await client.post("/api/admin/login", json={"phone": phone, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def _create_user(client: AsyncClient, phone="13900100001", password="user123", nickname="普通用户"):
    resp = await client.post("/api/auth/register", json={
        "phone": phone, "password": password, "nickname": nickname,
    })
    assert resp.status_code == 200
    return resp.json()


async def _user_headers(client: AsyncClient, phone="13900100001", password="user123"):
    resp = await client.post("/api/auth/login", json={"phone": phone, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_session(db_session, user_id: int, title="测试对话", msg_content="你好") -> ChatSession:
    session = ChatSession(
        user_id=user_id,
        session_type=SessionType.health_qa,
        title=title,
        message_count=1,
    )
    db_session.add(session)
    await db_session.flush()

    msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content=msg_content,
        message_type=MessageType.text,
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(session)
    return session


# ────────────── 管理端 API 测试 ──────────────


@pytest.mark.asyncio
async def test_tc001_admin_list_sessions(client: AsyncClient, db_session):
    """TC-001: 管理员可获取对话列表"""
    admin = await _create_admin(db_session)
    headers = await _admin_headers(client)

    reg = await _create_user(client)
    user_id = reg["user"]["id"]
    await _seed_session(db_session, user_id)

    resp = await client.get("/api/admin/chat-sessions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_tc002_admin_list_sessions_unauthorized(client: AsyncClient):
    """TC-002: 未登录返回401"""
    resp = await client.get("/api/admin/chat-sessions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tc003_admin_list_sessions_forbidden(client: AsyncClient):
    """TC-003: 非admin角色返回403"""
    await _create_user(client, phone="13900100003")
    headers = await _user_headers(client, phone="13900100003")

    resp = await client.get("/api/admin/chat-sessions", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tc004_admin_list_sessions_search(client: AsyncClient, db_session):
    """TC-004: 按用户搜索筛选"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    await _create_user(client, phone="13900100004", nickname="张三搜索")
    reg2 = await _create_user(client, phone="13900100044", nickname="李四其他")

    async with test_session() as s:
        u1_result = await s.execute(
            __import__("sqlalchemy").select(User).where(User.phone == "13900100004")
        )
        u1 = u1_result.scalar_one()
        u2_result = await s.execute(
            __import__("sqlalchemy").select(User).where(User.phone == "13900100044")
        )
        u2 = u2_result.scalar_one()

    await _seed_session(db_session, u1.id, title="张三的对话")
    await _seed_session(db_session, u2.id, title="李四的对话")

    resp = await client.get("/api/admin/chat-sessions", params={"user_search": "张三"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "张三" in (item.get("user_nickname") or "")


@pytest.mark.asyncio
async def test_tc005_admin_get_session_detail(client: AsyncClient, db_session):
    """TC-005: 获取对话详情"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    reg = await _create_user(client, phone="13900100005")
    user_id = reg["user"]["id"]
    session = await _seed_session(db_session, user_id, title="详情测试", msg_content="测试消息内容")

    resp = await client.get(f"/api/admin/chat-sessions/{session.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session.id
    assert data["title"] == "详情测试"
    assert "messages" in data
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["content"] == "测试消息内容"


@pytest.mark.asyncio
async def test_tc006_admin_get_session_not_found(client: AsyncClient, db_session):
    """TC-006: 不存在的对话返回404"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/chat-sessions/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tc007_admin_export_csv(client: AsyncClient, db_session):
    """TC-007: 导出CSV"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    reg = await _create_user(client, phone="13900100007")
    user_id = reg["user"]["id"]
    session = await _seed_session(db_session, user_id, msg_content="导出测试")

    resp = await client.get(
        f"/api/admin/chat-sessions/{session.id}/export",
        params={"format": "csv"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    body = resp.text
    assert "导出测试" in body


# ────────────── 用户端 API 测试 ──────────────


@pytest.mark.asyncio
async def test_tc008_user_list_sessions(client: AsyncClient, db_session):
    """TC-008: 获取当前用户的对话列表"""
    reg = await _create_user(client, phone="13900100008")
    headers = await _user_headers(client, phone="13900100008")
    user_id = reg["user"]["id"]

    await _seed_session(db_session, user_id)

    resp = await client.get("/api/chat-sessions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_tc009_user_list_sessions_unauthorized(client: AsyncClient):
    """TC-009: 未登录返回401"""
    resp = await client.get("/api/chat-sessions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tc010_user_get_session_detail(client: AsyncClient, db_session):
    """TC-010: 获取对话详情"""
    reg = await _create_user(client, phone="13900100010")
    headers = await _user_headers(client, phone="13900100010")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id, title="用户详情", msg_content="详情消息")

    resp = await client.get(f"/api/chat-sessions/{session.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session.id
    assert data["title"] == "用户详情"
    assert "messages" in data
    assert len(data["messages"]) >= 1


@pytest.mark.asyncio
async def test_tc011_user_rename_session(client: AsyncClient, db_session):
    """TC-011: 重命名标题"""
    reg = await _create_user(client, phone="13900100011")
    headers = await _user_headers(client, phone="13900100011")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id, title="旧标题")

    resp = await client.put(
        f"/api/chat-sessions/{session.id}",
        json={"title": "新标题"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新标题"


@pytest.mark.asyncio
async def test_tc012_user_pin_session(client: AsyncClient, db_session):
    """TC-012: 置顶对话"""
    reg = await _create_user(client, phone="13900100012")
    headers = await _user_headers(client, phone="13900100012")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id)

    resp = await client.put(
        f"/api/chat-sessions/{session.id}/pin",
        json={"is_pinned": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_pinned"] is True

    resp2 = await client.put(
        f"/api/chat-sessions/{session.id}/pin",
        json={"is_pinned": False},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_pinned"] is False


@pytest.mark.asyncio
async def test_tc013_user_delete_session(client: AsyncClient, db_session):
    """TC-013: 软删除对话"""
    reg = await _create_user(client, phone="13900100013")
    headers = await _user_headers(client, phone="13900100013")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id)

    resp = await client.delete(f"/api/chat-sessions/{session.id}", headers=headers)
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["message"]


@pytest.mark.asyncio
async def test_tc014_deleted_session_not_in_list(client: AsyncClient, db_session):
    """TC-014: 已删除的对话不再出现在列表中"""
    reg = await _create_user(client, phone="13900100014")
    headers = await _user_headers(client, phone="13900100014")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id, title="将被删除")

    await client.delete(f"/api/chat-sessions/{session.id}", headers=headers)

    resp = await client.get("/api/chat-sessions", headers=headers)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert session.id not in ids


@pytest.mark.asyncio
async def test_tc015_user_share_session(client: AsyncClient, db_session):
    """TC-015: 生成分享链接"""
    reg = await _create_user(client, phone="13900100015")
    headers = await _user_headers(client, phone="13900100015")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id)

    resp = await client.post(f"/api/chat-sessions/{session.id}/share", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "share_token" in data
    assert "share_url" in data
    assert len(data["share_token"]) > 0

    resp2 = await client.post(f"/api/chat-sessions/{session.id}/share", headers=headers)
    assert resp2.json()["share_token"] == data["share_token"]


# ────────────── 分享页 API 测试 ──────────────


@pytest.mark.asyncio
async def test_tc016_shared_chat_access(client: AsyncClient, db_session):
    """TC-016: 获取分享内容（无需认证）"""
    reg = await _create_user(client, phone="13900100016")
    headers = await _user_headers(client, phone="13900100016")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id, title="分享对话", msg_content="分享内容")

    share_resp = await client.post(f"/api/chat-sessions/{session.id}/share", headers=headers)
    token = share_resp.json()["share_token"]

    resp = await client.get(f"/api/shared/chat/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "分享对话"
    assert data["message_count"] >= 0
    assert "messages" in data
    assert any(m["content"] == "分享内容" for m in data["messages"])


@pytest.mark.asyncio
async def test_tc017_shared_chat_invalid_token(client: AsyncClient):
    """TC-017: 无效token返回404"""
    resp = await client.get("/api/shared/chat/invalid_token_abc123")
    assert resp.status_code == 404


# ────────────── 数据隔离测试 ──────────────


@pytest.mark.asyncio
async def test_tc018_user_isolation(client: AsyncClient, db_session):
    """TC-018: 用户A无法访问用户B的对话"""
    reg_a = await _create_user(client, phone="13900100018", nickname="用户A")
    reg_b = await _create_user(client, phone="13900100028", nickname="用户B")

    headers_a = await _user_headers(client, phone="13900100018")
    headers_b = await _user_headers(client, phone="13900100028")

    user_b_id = reg_b["user"]["id"]
    session_b = await _seed_session(db_session, user_b_id, title="用户B的对话")

    resp = await client.get(f"/api/chat-sessions/{session_b.id}", headers=headers_a)
    assert resp.status_code == 404

    resp2 = await client.put(
        f"/api/chat-sessions/{session_b.id}",
        json={"title": "被篡改"},
        headers=headers_a,
    )
    assert resp2.status_code == 404

    resp3 = await client.delete(f"/api/chat-sessions/{session_b.id}", headers=headers_a)
    assert resp3.status_code == 404

    resp4 = await client.get(f"/api/chat-sessions/{session_b.id}", headers=headers_b)
    assert resp4.status_code == 200
    assert resp4.json()["title"] == "用户B的对话"
