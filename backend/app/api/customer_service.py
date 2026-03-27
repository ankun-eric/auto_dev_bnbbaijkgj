from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    CSSessionStatus,
    CSSessionType,
    CSSenderType,
    CustomerServiceMessage,
    CustomerServiceSession,
    User,
)
from app.services.ai_service import ai_customer_service

router = APIRouter(prefix="/api/cs", tags=["客服"])


@router.post("/sessions")
async def create_cs_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomerServiceSession).where(
            CustomerServiceSession.user_id == current_user.id,
            CustomerServiceSession.status.in_([CSSessionStatus.waiting, CSSessionStatus.active]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "id": existing.id,
            "status": existing.status.value if hasattr(existing.status, "value") else existing.status,
            "type": existing.type.value if hasattr(existing.type, "value") else existing.type,
            "created_at": existing.created_at.isoformat(),
        }

    session = CustomerServiceSession(
        user_id=current_user.id,
        status=CSSessionStatus.active,
        type=CSSessionType.ai,
    )
    db.add(session)
    await db.flush()

    welcome = CustomerServiceMessage(
        session_id=session.id,
        sender_type=CSSenderType.ai,
        content="您好！我是宾尼小康AI客服助手，很高兴为您服务。请问有什么可以帮助您的？",
        message_type="text",
    )
    db.add(welcome)
    await db.flush()
    await db.refresh(session)

    return {
        "id": session.id,
        "status": session.status.value if hasattr(session.status, "value") else session.status,
        "type": session.type.value if hasattr(session.type, "value") else session.type,
        "created_at": session.created_at.isoformat(),
    }


@router.get("/sessions")
async def list_cs_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(CustomerServiceSession.id)).where(CustomerServiceSession.user_id == current_user.id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(CustomerServiceSession)
        .where(CustomerServiceSession.user_id == current_user.id)
        .order_by(CustomerServiceSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = result.scalars().all()
    items = [
        {
            "id": s.id,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "type": s.type.value if hasattr(s.type, "value") else s.type,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}/messages")
async def list_cs_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomerServiceSession).where(
            CustomerServiceSession.id == session_id,
            CustomerServiceSession.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")

    total_result = await db.execute(
        select(func.count(CustomerServiceMessage.id)).where(CustomerServiceMessage.session_id == session_id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(CustomerServiceMessage)
        .where(CustomerServiceMessage.session_id == session_id)
        .order_by(CustomerServiceMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = result.scalars().all()
    items = [
        {
            "id": m.id,
            "sender_type": m.sender_type.value if hasattr(m.sender_type, "value") else m.sender_type,
            "sender_id": m.sender_id,
            "content": m.content,
            "message_type": m.message_type,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/sessions/{session_id}/messages")
async def send_cs_message(
    session_id: int,
    content: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomerServiceSession).where(
            CustomerServiceSession.id == session_id,
            CustomerServiceSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    status_val = session.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val == "closed":
        raise HTTPException(status_code=400, detail="会话已关闭")

    user_msg = CustomerServiceMessage(
        session_id=session_id,
        sender_type=CSSenderType.user,
        sender_id=current_user.id,
        content=content,
        message_type="text",
    )
    db.add(user_msg)
    await db.flush()

    session_type_val = session.type
    if hasattr(session_type_val, "value"):
        session_type_val = session_type_val.value

    if session_type_val == "ai":
        history_result = await db.execute(
            select(CustomerServiceMessage)
            .where(CustomerServiceMessage.session_id == session_id)
            .order_by(CustomerServiceMessage.created_at.desc())
            .limit(10)
        )
        history = list(reversed(history_result.scalars().all()))
        context = []
        for msg in history:
            st = msg.sender_type
            if hasattr(st, "value"):
                st = st.value
            role = "user" if st == "user" else "assistant"
            context.append({"role": role, "content": msg.content})

        ai_reply = await ai_customer_service(content, context, db)

        ai_msg = CustomerServiceMessage(
            session_id=session_id,
            sender_type=CSSenderType.ai,
            content=ai_reply,
            message_type="text",
        )
        db.add(ai_msg)
        await db.flush()

        return {
            "user_message": {"content": content},
            "ai_reply": {"content": ai_reply},
        }

    return {"user_message": {"content": content}, "ai_reply": None}


@router.put("/sessions/{session_id}/transfer")
async def transfer_to_human(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomerServiceSession).where(
            CustomerServiceSession.id == session_id,
            CustomerServiceSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    session.type = CSSessionType.human
    session.status = CSSessionStatus.waiting

    system_msg = CustomerServiceMessage(
        session_id=session_id,
        sender_type=CSSenderType.ai,
        content="正在为您转接人工客服，请稍候...",
        message_type="text",
    )
    db.add(system_msg)

    return {"message": "正在转接人工客服"}
