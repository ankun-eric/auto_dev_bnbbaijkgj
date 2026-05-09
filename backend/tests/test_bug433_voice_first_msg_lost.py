"""[Bug-433 2026-05-09] AI 对话首页 - 语音/预设按钮"会话首句消息丢失"修复 — 后端契约测试。

覆盖范围（与 cursor_prompt_433 §5.5.1 / §6 验收清单 一致）：

- T01：流式接口入参 source='text'  → user 消息入库且 source='text'，AI 消息 parent_id 指向 user
- T02：流式接口入参 source='voice' → user 消息入库且 source='voice'
- T03：流式接口入参 source='preset' → user 消息入库且 source='preset'
- T04：流式接口未传 source → 默认 source='text'
- T05：流式接口入参 source 非法值 → 路由层归一化为 'text'，仍 200
- T06：非流式 fallback 接口 POST /messages 同样支持 source 字段
- T07：parent_id 字段存在且 user 消息为 NULL、AI 消息关联到 user.id
- T08：source 字段为 NOT NULL DEFAULT 'text'（数据库 schema 校验）

注意：
- 本测试在 SQLite + create_all 下运行，模型层声明的 source/parent_id 列会自动建到表里。
- 生产环境的 MySQL 字段迁移由 backend/app/main.py::_migrate_bug433_chat_message_source_parent_id 在
  应用启动时幂等执行，本文件聚焦在接口契约和模型字段层的回归。
- AI 实际生成走 mock：直接 patch app.api.chat.call_ai_model_stream / call_ai_model 让测试不依赖
  外部 LLM 网关。
"""
import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select


# ──────── 公共工具 ────────


async def _create_session(client: AsyncClient, auth_headers) -> int:
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "title": "Bug-433 测试会话"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _patch_llm_stream(monkeypatch, full_text: str = "你好，我是小康。"):
    """把 call_ai_model_stream 替换成确定性输出，避免依赖真实 LLM。"""

    async def _fake_stream(messages, system_prompt, db, *args, **kwargs):
        # 模拟两段 delta + 一段 done，mimic 真实 SSE 协议
        yield {"type": "delta", "content": full_text[: len(full_text) // 2], "_full": full_text[: len(full_text) // 2]}
        yield {"type": "delta", "content": full_text[len(full_text) // 2:], "_full": full_text}
        yield {"type": "done", "content": full_text}

    monkeypatch.setattr("app.api.chat.call_ai_model_stream", _fake_stream)


async def _consume_stream(client: AsyncClient, sid: int, body: dict, auth_headers):
    """调用流式接口并消费完整响应，返回 (status_code, accumulated_done_payload | None)。"""
    async with client.stream(
        "POST",
        f"/api/chat/sessions/{sid}/stream",
        json=body,
        headers=auth_headers,
    ) as resp:
        if resp.status_code != 200:
            text = await resp.aread()
            return resp.status_code, text.decode("utf-8", errors="ignore")
        done_payload = None
        async for line in resp.aiter_lines():
            if line.startswith("data: ") and "message_id" in line:
                try:
                    done_payload = json.loads(line[len("data: "):])
                except Exception:
                    pass
        return 200, done_payload


# ──────── T01 / T02 / T03：source 三种合法值正确入库 ────────


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["text", "voice", "preset"])
async def test_t01_t02_t03_stream_source_persisted(
    client: AsyncClient, auth_headers, db_session, monkeypatch, source
):
    """流式接口分别用 text/voice/preset 发送，user 消息入库 source 正确，AI 消息 parent_id 指向 user。"""
    await _patch_llm_stream(monkeypatch, full_text=f"AI 回复 {source}")
    sid = await _create_session(client, auth_headers)

    status, _ = await _consume_stream(
        client,
        sid,
        {"content": f"我今天该吃什么? ({source})", "message_type": "text", "source": source},
        auth_headers,
    )
    assert status == 200

    from app.models.models import ChatMessage, MessageRole
    rows = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at.asc())
        )
    ).scalars().all()
    # 至少有 user + ai 两条
    user_rows = [r for r in rows if (r.role.value if hasattr(r.role, "value") else r.role) == "user"]
    ai_rows = [r for r in rows if (r.role.value if hasattr(r.role, "value") else r.role) == "assistant"]
    assert user_rows, "user 消息必须入库（强约束）"
    assert ai_rows, "AI 回复也应入库"
    assert user_rows[-1].source == source, f"user.source 应为 {source}"
    assert ai_rows[-1].parent_id == user_rows[-1].id, "AI 消息 parent_id 应关联到对应 user 消息"


# ──────── T04：未传 source 默认 'text' ────────


@pytest.mark.asyncio
async def test_t04_stream_default_source_text(
    client: AsyncClient, auth_headers, db_session, monkeypatch
):
    await _patch_llm_stream(monkeypatch)
    sid = await _create_session(client, auth_headers)
    status, _ = await _consume_stream(
        client,
        sid,
        {"content": "默认 source 测试", "message_type": "text"},
        auth_headers,
    )
    assert status == 200
    from app.models.models import ChatMessage
    rows = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sid)
        )
    ).scalars().all()
    user_row = next(r for r in rows if (r.role.value if hasattr(r.role, "value") else r.role) == "user")
    assert user_row.source == "text", "未传 source 时默认应为 'text'"


# ──────── T05：source 非法值归一化为 'text' ────────


@pytest.mark.asyncio
async def test_t05_stream_invalid_source_normalized(
    client: AsyncClient, auth_headers, db_session, monkeypatch
):
    await _patch_llm_stream(monkeypatch)
    sid = await _create_session(client, auth_headers)
    status, _ = await _consume_stream(
        client,
        sid,
        {"content": "非法 source 测试", "message_type": "text", "source": "totally_unknown_source"},
        auth_headers,
    )
    assert status == 200
    from app.models.models import ChatMessage
    rows = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sid)
        )
    ).scalars().all()
    user_row = next(r for r in rows if (r.role.value if hasattr(r.role, "value") else r.role) == "user")
    assert user_row.source == "text", "非法 source 应被路由层归一化为 'text'"


# ──────── T06：fallback 接口 POST /messages 同样支持 source ────────


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["text", "voice", "preset"])
async def test_t06_fallback_messages_endpoint_source(
    client: AsyncClient, auth_headers, db_session, monkeypatch, source
):
    """非流式 fallback 接口 POST /api/chat/sessions/{id}/messages 也接受 source 字段。"""

    async def _fake_call(messages, system_prompt, db, return_usage=False, *args, **kwargs):
        if return_usage:
            return {"content": "fallback 回复", "usage": None, "model": "mock-llm"}
        return "fallback 回复"

    monkeypatch.setattr("app.api.chat.call_ai_model", _fake_call)

    sid = await _create_session(client, auth_headers)
    resp = await client.post(
        f"/api/chat/sessions/{sid}/messages",
        json={"content": f"fallback 测试 {source}", "message_type": "text", "source": source},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text

    from app.models.models import ChatMessage
    rows = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at.asc())
        )
    ).scalars().all()
    user_row = next(r for r in rows if (r.role.value if hasattr(r.role, "value") else r.role) == "user")
    ai_row = next(r for r in rows if (r.role.value if hasattr(r.role, "value") else r.role) == "assistant")
    assert user_row.source == source
    assert ai_row.parent_id == user_row.id


# ──────── T07：parent_id 字段语义校验 ────────


@pytest.mark.asyncio
async def test_t07_parent_id_semantics(
    client: AsyncClient, auth_headers, db_session, monkeypatch
):
    """user 消息的 parent_id 应为 NULL；AI 消息的 parent_id 应指向同会话的某条 user 消息。"""
    await _patch_llm_stream(monkeypatch)
    sid = await _create_session(client, auth_headers)
    status, _ = await _consume_stream(
        client,
        sid,
        {"content": "parent_id 语义测试", "source": "voice"},
        auth_headers,
    )
    assert status == 200
    from app.models.models import ChatMessage
    rows = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at.asc())
        )
    ).scalars().all()
    user_ids = {r.id for r in rows if (r.role.value if hasattr(r.role, "value") else r.role) == "user"}
    for r in rows:
        role = r.role.value if hasattr(r.role, "value") else r.role
        if role == "user":
            assert r.parent_id is None, "user 消息的 parent_id 必须为 NULL"
        elif role == "assistant":
            assert r.parent_id in user_ids, "AI 消息的 parent_id 必须指向同会话的某条 user 消息"


# ──────── T08：source 字段 schema 校验（NOT NULL DEFAULT 'text'） ────────


@pytest.mark.asyncio
async def test_t08_source_field_schema(db_session):
    """模型层 ChatMessage.source 必须为 NOT NULL DEFAULT 'text'：直接 INSERT 不写 source 应得到 'text'。"""
    from app.models.models import ChatMessage, ChatSession, MessageRole, SessionType, User
    from app.core.security import get_password_hash

    user = User(
        phone="13700000099",
        password_hash=get_password_hash("test"),
        nickname="schema_test",
    )
    db_session.add(user)
    await db_session.flush()

    session = ChatSession(user_id=user.id, session_type=SessionType.health_qa, title="schema_test")
    db_session.add(session)
    await db_session.flush()

    msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content="不显式传 source",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)
    assert msg.source == "text", "ChatMessage.source 默认值必须为 'text'"
    assert msg.parent_id is None, "ChatMessage.parent_id 默认必须为 NULL"
