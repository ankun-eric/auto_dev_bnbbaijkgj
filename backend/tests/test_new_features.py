"""
新功能接口自动化测试:
- DrugIdentifyDetail 新增 family_member_id
- POST /api/chat/sessions/{session_id}/stream (SSE)
- GET /api/settings/tts-config (公开)
- GET /api/admin/settings/tts-config (管理员)
- PUT /api/admin/settings/tts-config (管理员)
- POST /api/tts/synthesize
- POST /api/chat/share
- GET /api/share/{share_token}
- POST /api/chat/share/poster
- GET /api/admin/settings/share-config
- PUT /api/admin/settings/share-config
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import (
    ChatMessage,
    ChatSession,
    DrugIdentifyDetail,
    FamilyMember,
    MessageRole,
    MessageType,
    SessionType,
    SystemConfig,
    User,
    UserRole,
)

from tests.conftest import test_session


# ──── helpers ────


async def _get_user_id(client: AsyncClient, headers: dict) -> int:
    resp = await client.get("/api/auth/me", headers=headers)
    return resp.json()["id"]


async def _create_session_and_messages(db_session, user_id: int):
    """Create a chat session with a user message and an AI reply, return (session, user_msg, ai_msg)."""
    session = ChatSession(
        user_id=user_id,
        session_type="health_qa",
        title="测试对话",
    )
    db_session.add(session)
    await db_session.flush()
    await db_session.refresh(session)

    user_msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content="我头疼怎么办？",
        message_type="text",
    )
    db_session.add(user_msg)
    await db_session.flush()
    await db_session.refresh(user_msg)

    ai_msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.assistant,
        content="建议您注意休息，如果持续头痛请及时就医。",
        message_type="text",
    )
    db_session.add(ai_msg)
    await db_session.flush()
    await db_session.refresh(ai_msg)

    await db_session.commit()
    return session, user_msg, ai_msg


async def _enable_tts(db_session, api_key="test_key_123"):
    """Insert a TTS config with enabled=True into SystemConfig."""
    config = SystemConfig(
        config_key="tts_config",
        config_value=json.dumps({
            "enabled": True,
            "cloud_provider": "aliyun",
            "cloud_api_key": api_key,
            "voice_gender": "female",
            "speed": 1.0,
            "pitch": 1.0,
        }),
        config_type="json",
    )
    db_session.add(config)
    await db_session.flush()


# ════════════════════════════════════════════════════════════════════
# 1. DrugIdentifyDetail — family_member_id
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_drug_detail_with_family_member_id(client: AsyncClient, auth_headers, db_session):
    """DrugIdentifyDetail 可关联 family_member_id。"""
    user_id = await _get_user_id(client, auth_headers)

    member = FamilyMember(
        user_id=user_id,
        nickname="妈妈",
        relationship_type="母亲",
        gender="female",
    )
    db_session.add(member)
    await db_session.flush()
    await db_session.refresh(member)

    record = DrugIdentifyDetail(
        user_id=user_id,
        drug_name="阿司匹林",
        provider_name="test",
        status="success",
        family_member_id=member.id,
    )
    db_session.add(record)
    await db_session.flush()
    await db_session.refresh(record)

    assert record.family_member_id == member.id


@pytest.mark.asyncio
async def test_drug_detail_family_member_id_nullable(client: AsyncClient, auth_headers, db_session):
    """DrugIdentifyDetail.family_member_id 可为 None。"""
    user_id = await _get_user_id(client, auth_headers)

    record = DrugIdentifyDetail(
        user_id=user_id,
        drug_name="布洛芬",
        provider_name="test",
        status="success",
        family_member_id=None,
    )
    db_session.add(record)
    await db_session.flush()
    await db_session.refresh(record)

    assert record.family_member_id is None


@pytest.mark.asyncio
async def test_drug_history_contains_family_member_id(client: AsyncClient, auth_headers, db_session):
    """GET /api/drug-identify/history 返回的数据中包含 family_member_id 字段。"""
    resp = await client.get(
        "/api/drug-identify/history",
        headers=auth_headers,
        params={"page": 1, "page_size": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


# ════════════════════════════════════════════════════════════════════
# 2. POST /api/chat/sessions/{session_id}/stream — SSE 流式输出
# ════════════════════════════════════════════════════════════════════


async def _fake_stream(messages, system_prompt, db):
    yield {"type": "delta", "content": "你好", "_full": "你好"}
    yield {"type": "done", "content": "你好，请描述您的症状。"}


@pytest.mark.asyncio
@patch("app.api.chat.call_ai_model_stream", side_effect=_fake_stream)
@patch("app.api.chat.search_knowledge", new_callable=AsyncMock, return_value={"hits": []})
async def test_stream_message_success(mock_kb, mock_stream, client: AsyncClient, auth_headers):
    """SSE 流式接口正常返回 event-stream 响应。"""
    session_resp = await client.post("/api/chat/sessions", json={
        "session_type": "health_qa",
        "title": "流式测试",
    }, headers=auth_headers)
    assert session_resp.status_code == 200
    session_id = session_resp.json()["id"]

    resp = await client.post(f"/api/chat/sessions/{session_id}/stream", json={
        "content": "你好",
        "message_type": "text",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_stream_message_unauthorized(client: AsyncClient):
    """SSE 流式接口未认证返回 401。"""
    resp = await client.post("/api/chat/sessions/1/stream", json={
        "content": "hello",
        "message_type": "text",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
@patch("app.api.chat.call_ai_model_stream", side_effect=_fake_stream)
@patch("app.api.chat.search_knowledge", new_callable=AsyncMock, return_value={"hits": []})
async def test_stream_message_invalid_session(mock_kb, mock_stream, client: AsyncClient, auth_headers):
    """SSE 流式接口：不存在的会话返回 404。"""
    resp = await client.post("/api/chat/sessions/99999/stream", json={
        "content": "hello",
        "message_type": "text",
    }, headers=auth_headers)
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# 3. GET /api/settings/tts-config — 公开 TTS 配置
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_tts_config_success(client: AsyncClient, auth_headers):
    """已登录用户获取 TTS 公开配置。"""
    resp = await client.get("/api/settings/tts-config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "default_mode" in data
    assert "voice_gender" in data


@pytest.mark.asyncio
async def test_get_tts_config_unauthorized(client: AsyncClient):
    """未认证访问 TTS 配置返回 401。"""
    resp = await client.get("/api/settings/tts-config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_tts_config_with_platform(client: AsyncClient, auth_headers):
    """传入 platform 参数获取特定平台 TTS 配置。"""
    resp = await client.get(
        "/api/settings/tts-config",
        params={"platform": "miniprogram"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "platform_override" in data


# ════════════════════════════════════════════════════════════════════
# 4. GET /api/admin/settings/tts-config — 管理员获取完整 TTS 配置
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_get_tts_config_success(client: AsyncClient, admin_headers):
    """管理员获取完整 TTS 配置（含 API key）。"""
    resp = await client.get("/api/admin/settings/tts-config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "cloud_api_key" in data
    assert "h5_mode" in data


@pytest.mark.asyncio
async def test_admin_get_tts_config_forbidden_for_user(client: AsyncClient, auth_headers):
    """普通用户无权访问管理员 TTS 配置。"""
    resp = await client.get("/api/admin/settings/tts-config", headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_get_tts_config_unauthorized(client: AsyncClient):
    """未认证访问管理员 TTS 配置返回 401。"""
    resp = await client.get("/api/admin/settings/tts-config")
    assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# 5. PUT /api/admin/settings/tts-config — 管理员更新 TTS 配置
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_update_tts_config_success(client: AsyncClient, admin_headers):
    """管理员更新 TTS 配置成功。"""
    resp = await client.put("/api/admin/settings/tts-config", json={
        "enabled": True,
        "cloud_provider": "tencent",
        "speed": 1.5,
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["cloud_provider"] == "tencent"
    assert data["speed"] == 1.5


@pytest.mark.asyncio
async def test_admin_update_tts_config_forbidden_for_user(client: AsyncClient, auth_headers):
    """普通用户无权更新 TTS 配置。"""
    resp = await client.put("/api/admin/settings/tts-config", json={
        "enabled": True,
    }, headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_update_tts_config_unauthorized(client: AsyncClient):
    """未认证更新 TTS 配置返回 401。"""
    resp = await client.put("/api/admin/settings/tts-config", json={"enabled": True})
    assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# 6. POST /api/tts/synthesize — TTS 语音合成
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tts_synthesize_disabled(client: AsyncClient, auth_headers):
    """TTS 未启用时合成应返回 400。"""
    resp = await client.post("/api/tts/synthesize", json={
        "text": "你好世界",
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "未启用" in resp.json()["detail"]


@pytest.mark.asyncio
@patch("app.api.tts._synthesize_aliyun", new_callable=AsyncMock, return_value=b"\x00\x01\x02")
async def test_tts_synthesize_success(mock_synth, client: AsyncClient, auth_headers, db_session):
    """TTS 启用且配置正确时合成成功。"""
    await _enable_tts(db_session)

    resp = await client.post("/api/tts/synthesize", json={
        "text": "测试语音合成",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "audio_url" in data
    assert data["text_length"] == 6
    assert data["provider"] == "aliyun"


@pytest.mark.asyncio
async def test_tts_synthesize_unauthorized(client: AsyncClient):
    """未认证调用 TTS 合成返回 401。"""
    resp = await client.post("/api/tts/synthesize", json={"text": "hello"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tts_synthesize_empty_text(client: AsyncClient, auth_headers, db_session):
    """空文本调用 TTS 合成应返回 400。"""
    await _enable_tts(db_session)
    resp = await client.post("/api/tts/synthesize", json={
        "text": "   ",
    }, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_tts_synthesize_text_too_long(client: AsyncClient, auth_headers, db_session):
    """文本超长调用 TTS 合成应返回 400。"""
    await _enable_tts(db_session)
    resp = await client.post("/api/tts/synthesize", json={
        "text": "测" * 5001,
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "5000" in resp.json()["detail"]


# ════════════════════════════════════════════════════════════════════
# 7. POST /api/chat/share — 创建分享链接
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_chat_share_success(client: AsyncClient, auth_headers, db_session):
    """创建对话分享链接成功（传入 user message id）。"""
    user_id = await _get_user_id(client, auth_headers)
    session, user_msg, ai_msg = await _create_session_and_messages(db_session, user_id)

    resp = await client.post("/api/chat/share", json={
        "session_id": session.id,
        "message_id": user_msg.id,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "share_token" in data
    assert "share_url" in data
    assert len(data["share_token"]) > 0


@pytest.mark.asyncio
async def test_create_chat_share_unauthorized(client: AsyncClient):
    """未认证创建分享链接返回 401。"""
    resp = await client.post("/api/chat/share", json={
        "session_id": 1,
        "message_id": 1,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_chat_share_session_not_found(client: AsyncClient, auth_headers):
    """不存在的会话创建分享返回 404。"""
    resp = await client.post("/api/chat/share", json={
        "session_id": 99999,
        "message_id": 1,
    }, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_chat_share_missing_fields(client: AsyncClient, auth_headers):
    """缺少必填字段返回 422。"""
    resp = await client.post("/api/chat/share", json={}, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_chat_share_idempotent(client: AsyncClient, auth_headers, db_session):
    """重复创建分享链接返回相同 token。"""
    user_id = await _get_user_id(client, auth_headers)
    session, user_msg, ai_msg = await _create_session_and_messages(db_session, user_id)

    resp1 = await client.post("/api/chat/share", json={
        "session_id": session.id,
        "message_id": user_msg.id,
    }, headers=auth_headers)
    resp2 = await client.post("/api/chat/share", json={
        "session_id": session.id,
        "message_id": user_msg.id,
    }, headers=auth_headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["share_token"] == resp2.json()["share_token"]


# ════════════════════════════════════════════════════════════════════
# 8. GET /api/share/{share_token} — 查看分享内容（公开）
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_view_shared_conversation_success(client: AsyncClient, auth_headers, db_session):
    """公开访问分享链接成功。"""
    user_id = await _get_user_id(client, auth_headers)
    session, user_msg, ai_msg = await _create_session_and_messages(db_session, user_id)

    share_resp = await client.post("/api/chat/share", json={
        "session_id": session.id,
        "message_id": user_msg.id,
    }, headers=auth_headers)
    assert share_resp.status_code == 200
    token = share_resp.json()["share_token"]

    resp = await client.get(f"/api/share/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_title"] == "测试对话"
    assert data["user_message"]["role"] == "user"
    assert data["ai_message"]["role"] == "assistant"
    assert data["view_count"] >= 1


@pytest.mark.asyncio
async def test_view_shared_conversation_not_found(client: AsyncClient):
    """不存在的分享 token 返回 404。"""
    resp = await client.get("/api/share/nonexistent_token_abcdef1234567890")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_view_shared_conversation_increments_count(client: AsyncClient, auth_headers, db_session):
    """多次访问分享链接时 view_count 递增。"""
    user_id = await _get_user_id(client, auth_headers)
    session, user_msg, ai_msg = await _create_session_and_messages(db_session, user_id)

    share_resp = await client.post("/api/chat/share", json={
        "session_id": session.id,
        "message_id": user_msg.id,
    }, headers=auth_headers)
    assert share_resp.status_code == 200
    token = share_resp.json()["share_token"]

    resp1 = await client.get(f"/api/share/{token}")
    count1 = resp1.json()["view_count"]

    resp2 = await client.get(f"/api/share/{token}")
    count2 = resp2.json()["view_count"]

    assert count2 == count1 + 1


# ════════════════════════════════════════════════════════════════════
# 9. POST /api/chat/share/poster — 生成海报图片
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@patch("app.api.chat_share._generate_poster_image")
async def test_generate_poster_success(mock_gen, client: AsyncClient, auth_headers, db_session):
    """生成海报图片成功。"""
    user_id = await _get_user_id(client, auth_headers)
    session, user_msg, ai_msg = await _create_session_and_messages(db_session, user_id)

    resp = await client.post("/api/chat/share/poster", json={
        "session_id": session.id,
        "message_id": ai_msg.id,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "poster_url" in data
    mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_generate_poster_unauthorized(client: AsyncClient):
    """未认证生成海报返回 401。"""
    resp = await client.post("/api/chat/share/poster", json={
        "session_id": 1,
        "message_id": 1,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_poster_session_not_found(client: AsyncClient, auth_headers):
    """不存在的会话生成海报返回 404。"""
    resp = await client.post("/api/chat/share/poster", json={
        "session_id": 99999,
        "message_id": 1,
    }, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_poster_missing_fields(client: AsyncClient, auth_headers):
    """缺少必填参数返回 422。"""
    resp = await client.post("/api/chat/share/poster", json={}, headers=auth_headers)
    assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# 10. GET /api/admin/settings/share-config — 获取分享海报配置
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_get_share_config_success(client: AsyncClient, admin_headers):
    """管理员获取分享海报配置。"""
    resp = await client.get("/api/admin/settings/share-config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "product_name" in data
    assert "slogan" in data
    assert "background_color" in data
    assert "template" in data


@pytest.mark.asyncio
async def test_admin_get_share_config_forbidden_for_user(client: AsyncClient, auth_headers):
    """普通用户无权访问分享海报配置。"""
    resp = await client.get("/api/admin/settings/share-config", headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_get_share_config_unauthorized(client: AsyncClient):
    """未认证访问分享海报配置返回 401。"""
    resp = await client.get("/api/admin/settings/share-config")
    assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# 11. PUT /api/admin/settings/share-config — 更新分享海报配置
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_update_share_config_success(client: AsyncClient, admin_headers):
    """管理员更新分享海报配置。"""
    resp = await client.put("/api/admin/settings/share-config", json={
        "product_name": "健康宝",
        "slogan": "您的AI健康管家",
        "background_color": "#f0f0f0",
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "健康宝"
    assert data["slogan"] == "您的AI健康管家"
    assert data["background_color"] == "#f0f0f0"


@pytest.mark.asyncio
async def test_admin_update_share_config_forbidden_for_user(client: AsyncClient, auth_headers):
    """普通用户无权更新分享海报配置。"""
    resp = await client.put("/api/admin/settings/share-config", json={
        "product_name": "hack",
    }, headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_update_share_config_unauthorized(client: AsyncClient):
    """未认证更新分享海报配置返回 401。"""
    resp = await client.put("/api/admin/settings/share-config", json={"product_name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_update_share_config_partial(client: AsyncClient, admin_headers):
    """管理员可以部分更新分享海报配置。"""
    resp = await client.put("/api/admin/settings/share-config", json={
        "template": "modern",
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["template"] == "modern"
