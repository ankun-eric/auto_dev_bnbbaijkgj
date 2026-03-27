import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient, auth_headers):
    response = await client.post("/api/chat/sessions", json={
        "session_type": "health_qa",
        "title": "测试对话",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["session_type"] == "health_qa"
    assert data["title"] == "测试对话"
    assert "id" in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_create_session_default_title(client: AsyncClient, auth_headers):
    response = await client.post("/api/chat/sessions", json={
        "session_type": "symptom_check",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "新对话"


@pytest.mark.asyncio
async def test_create_session_unauthorized(client: AsyncClient):
    response = await client.post("/api/chat/sessions", json={
        "session_type": "health_qa",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, auth_headers):
    await client.post("/api/chat/sessions", json={
        "session_type": "health_qa",
        "title": "对话1",
    }, headers=auth_headers)
    await client.post("/api/chat/sessions", json={
        "session_type": "symptom_check",
        "title": "对话2",
    }, headers=auth_headers)

    response = await client.get("/api/chat/sessions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_sessions_filter_by_type(client: AsyncClient, auth_headers):
    await client.post("/api/chat/sessions", json={
        "session_type": "health_qa",
    }, headers=auth_headers)
    await client.post("/api/chat/sessions", json={
        "session_type": "symptom_check",
    }, headers=auth_headers)

    response = await client.get(
        "/api/chat/sessions", params={"session_type": "health_qa"}, headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
@patch("app.api.chat.call_ai_model", new_callable=AsyncMock, return_value="这是AI的回复内容")
async def test_send_message(mock_ai, client: AsyncClient, auth_headers):
    session_resp = await client.post("/api/chat/sessions", json={
        "session_type": "health_qa",
        "title": "测试对话",
    }, headers=auth_headers)
    session_id = session_resp.json()["id"]

    response = await client.post(f"/api/chat/sessions/{session_id}/messages", json={
        "content": "我头疼怎么办？",
        "message_type": "text",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert data["content"] == "这是AI的回复内容"
    assert data["session_id"] == session_id


@pytest.mark.asyncio
async def test_send_message_invalid_session(client: AsyncClient, auth_headers):
    response = await client.post("/api/chat/sessions/99999/messages", json={
        "content": "hello",
        "message_type": "text",
    }, headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.api.chat.call_ai_model", new_callable=AsyncMock, return_value="AI回复")
async def test_list_messages(mock_ai, client: AsyncClient, auth_headers):
    session_resp = await client.post("/api/chat/sessions", json={
        "session_type": "health_qa",
    }, headers=auth_headers)
    session_id = session_resp.json()["id"]

    await client.post(f"/api/chat/sessions/{session_id}/messages", json={
        "content": "你好",
        "message_type": "text",
    }, headers=auth_headers)

    response = await client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    roles = [m["role"] for m in data["items"]]
    assert "user" in roles
    assert "assistant" in roles
