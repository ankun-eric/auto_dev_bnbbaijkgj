import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_db
from app.core.security import get_current_user
from app.models.models import (
    AiDisclaimerConfig,
    AiPromptConfig,
    AiSensitiveWord,
    ChatMessage,
    ChatSession,
    MessageRole,
    MessageType,
    SessionType,
    User,
)
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatSessionCreate, ChatSessionResponse
from app.services.ai_service import call_ai_model, symptom_analysis
from app.services.knowledge_search import search_knowledge

router = APIRouter(prefix="/api/chat", tags=["AI对话"])

DEFAULT_SYSTEM_PROMPTS = {
    "health_qa": "你是「宾尼小康」AI健康咨询助手，一个专业、友好的健康咨询助手。请用通俗易懂的语言回答用户的健康相关问题，提供健康参考信息，并在必要时建议用户及时就医。所有内容仅供健康参考，不构成任何医疗诊断或治疗建议。",
    "symptom_check": "你是一位专业的AI健康自查助手。请根据用户描述的身体状况进行初步健康参考分析，给出可能的相关因素和健康建议。所有内容仅供自我健康参考，不能替代专业医疗检查，如有异常请尽快就医。",
    "tcm": "你是一位中医AI养生助手，精通中医养生理论。请根据用户描述，从中医养生角度提供调理建议。所有中医养生建议仅供参考，个人体质不同，建议在专业中医师指导下调理。",
    "drug_query": "你是一位药学AI用药参考助手，请提供药品的基本信息供用户参考，包括常见用法、注意事项、相互作用等。所有用药信息仅供参考，具体用药请严格遵医嘱，切勿自行用药。",
    "customer_service": "你是「宾尼小康」平台的AI客服助手，请热情友好地解答用户关于平台服务的问题。",
}


async def _get_system_prompt(session_type: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(AiPromptConfig).where(AiPromptConfig.chat_type == session_type)
    )
    config = result.scalar_one_or_none()
    if config and config.system_prompt:
        return config.system_prompt
    return DEFAULT_SYSTEM_PROMPTS.get(session_type, DEFAULT_SYSTEM_PROMPTS["health_qa"])


async def _filter_sensitive_words(content: str, db: AsyncSession) -> str:
    result = await db.execute(select(AiSensitiveWord))
    words = result.scalars().all()
    for w in words:
        content = content.replace(w.sensitive_word, w.replacement_word)
    return content


async def _append_disclaimer(content: str, session_type: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(AiDisclaimerConfig).where(AiDisclaimerConfig.chat_type == session_type)
    )
    config = result.scalar_one_or_none()
    if config and config.is_enabled and config.disclaimer_text:
        content += "\n\n---disclaimer---\n" + config.disclaimer_text
    return content


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(
        user_id=current_user.id,
        session_type=data.session_type,
        title=data.title or "新对话",
        family_member_id=data.family_member_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions")
async def list_sessions(
    session_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatSession).where(ChatSession.user_id == current_user.id)
    count_query = select(func.count(ChatSession.id)).where(ChatSession.user_id == current_user.id)

    if session_type:
        query = query.where(ChatSession.session_type == session_type)
        count_query = count_query.where(ChatSession.session_type == session_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(ChatSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ChatSessionResponse.model_validate(s) for s in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    total_result = await db.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ChatMessageResponse.model_validate(m) for m in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: int,
    data: ChatMessageCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    user_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.user,
        content=data.content,
        message_type=data.message_type,
        file_url=data.file_url,
    )
    db.add(user_msg)
    await db.flush()

    if not session.device_info:
        session.device_info = request.headers.get("User-Agent", "")[:500]
    if not session.ip_address:
        session.ip_address = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.client.host if request.client else None
        )

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(history_result.scalars().all()))

    messages = [{"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content} for m in history_msgs]

    session_type_val = session.session_type.value if hasattr(session.session_type, "value") else session.session_type
    system_prompt = await _get_system_prompt(session_type_val, db)

    knowledge_hits = []
    try:
        kb_result = await search_knowledge(
            data.content, session_type_val, db,
            session_id=session_id, message_id=None,
        )
        knowledge_hits = kb_result.get("hits", [])
        if knowledge_hits:
            kb_context_parts = []
            for hit in knowledge_hits:
                if hit.get("question"):
                    kb_context_parts.append(f"Q: {hit['question']}")
                if hit.get("content_json"):
                    content_val = hit["content_json"]
                    if isinstance(content_val, dict):
                        kb_context_parts.append(f"A: {json.dumps(content_val, ensure_ascii=False)}")
                    elif isinstance(content_val, str):
                        kb_context_parts.append(f"A: {content_val}")
                elif hit.get("title"):
                    kb_context_parts.append(f"A: {hit['title']}")
            if kb_context_parts:
                kb_context = "\n".join(kb_context_parts)
                system_prompt += f"\n\n以下是知识库中匹配到的参考信息，请优先参考这些内容回答用户问题：\n{kb_context}"
    except Exception:
        pass

    start_time = time.time()
    ai_result = await call_ai_model(messages, system_prompt, db, return_usage=True)
    elapsed_ms = int((time.time() - start_time) * 1000)

    ai_content = ai_result["content"]
    usage = ai_result.get("usage")
    model_used = ai_result.get("model")

    ai_content = await _filter_sensitive_words(ai_content, db)
    ai_content = await _append_disclaimer(ai_content, session_type_val, db)

    if not session.model_name and model_used:
        session.model_name = model_used

    ai_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.assistant,
        content=ai_content,
        message_type=MessageType.text,
        response_time_ms=elapsed_ms,
        prompt_tokens=usage.get("prompt_tokens") if usage else None,
        completion_tokens=usage.get("completion_tokens") if usage else None,
    )
    db.add(ai_msg)

    session.message_count = (session.message_count or 0) + 1

    if session.title == "新对话" and len(history_msgs) <= 2:
        session.title = data.content[:50]

    await db.flush()
    await db.refresh(ai_msg)

    resp = ChatMessageResponse.model_validate(ai_msg).model_dump()
    if knowledge_hits:
        resp["knowledge_hits"] = knowledge_hits
    return resp


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: int):
    await websocket.accept()

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="缺少认证token")
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub", 0))
    except JWTError:
        await websocket.close(code=4001, reason="无效的认证token")
        return

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            content = data.get("content", "")
            msg_type = data.get("message_type", "text")

            async with async_session() as db:
                result = await db.execute(
                    select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
                )
                session = result.scalar_one_or_none()
                if not session:
                    await websocket.send_json({"error": "会话不存在"})
                    continue

                user_msg = ChatMessage(
                    session_id=session_id,
                    role=MessageRole.user,
                    content=content,
                    message_type=msg_type,
                )
                db.add(user_msg)
                await db.flush()

                history_result = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(20)
                )
                history_msgs = list(reversed(history_result.scalars().all()))
                messages = [{"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content} for m in history_msgs]

                stype = session.session_type.value if hasattr(session.session_type, "value") else session.session_type
                system_prompt = await _get_system_prompt(stype, db)

                ai_reply = await call_ai_model(messages, system_prompt, db)

                ai_reply = await _filter_sensitive_words(ai_reply, db)
                ai_reply = await _append_disclaimer(ai_reply, stype, db)

                ai_msg = ChatMessage(
                    session_id=session_id,
                    role=MessageRole.assistant,
                    content=ai_reply,
                    message_type=MessageType.text,
                )
                db.add(ai_msg)
                await db.commit()

                await websocket.send_json({
                    "role": "assistant",
                    "content": ai_reply,
                    "message_type": "text",
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
