import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_db
from app.core.security import get_current_user
from app.models.models import ChatMessage, ChatSession, MessageRole, MessageType, SessionType, User
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatSessionCreate, ChatSessionResponse
from app.services.ai_service import call_ai_model, symptom_analysis

router = APIRouter(prefix="/api/chat", tags=["AI对话"])

SYSTEM_PROMPTS = {
    "health_qa": "你是「宾尼小康」AI健康管家，一个专业、友好的健康咨询助手。请用通俗易懂的语言回答用户的健康问题，并在必要时建议就医。声明仅供参考。",
    "symptom_check": "你是一位专业的AI症状分析助手。请根据用户描述的症状进行初步分析，给出可能的病因和建议。声明仅供参考，不构成医疗诊断。",
    "tcm": "你是一位中医AI辨证助手，精通中医理论。请根据用户描述，从中医角度进行分析和建议。",
    "drug_query": "你是一位药学AI顾问，请准确回答用户关于药品的问题，包括用法用量、注意事项、相互作用等。",
    "customer_service": "你是「宾尼小康」平台的AI客服助手，请热情友好地解答用户关于平台服务的问题。",
}


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

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(history_result.scalars().all()))

    messages = [{"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content} for m in history_msgs]

    system_prompt = SYSTEM_PROMPTS.get(
        session.session_type.value if hasattr(session.session_type, "value") else session.session_type,
        SYSTEM_PROMPTS["health_qa"],
    )

    ai_reply = await call_ai_model(messages, system_prompt, db)

    ai_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.assistant,
        content=ai_reply,
        message_type=MessageType.text,
    )
    db.add(ai_msg)

    if session.title == "新对话" and len(history_msgs) <= 2:
        session.title = data.content[:50]

    await db.flush()
    await db.refresh(ai_msg)
    return ChatMessageResponse.model_validate(ai_msg)


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
                system_prompt = SYSTEM_PROMPTS.get(stype, SYSTEM_PROMPTS["health_qa"])

                ai_reply = await call_ai_model(messages, system_prompt, db)

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
