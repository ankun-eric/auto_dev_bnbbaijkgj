import io
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import ChatMessage, ChatSession, MessageRole, User
from app.schemas.chat_history import (
    AdminChatMessageItem,
    AdminChatSessionDetail,
    AdminChatSessionItem,
    ChatSessionPinRequest,
    ChatSessionUpdate,
    SharedChatMessageItem,
    SharedChatResponse,
    UserChatSessionItem,
)

router = APIRouter(tags=["对话记录"])

admin_dep = require_role("admin")


# ──────────────── 管理端 API ────────────────


@router.get("/api/admin/chat-sessions")
async def admin_list_sessions(
    user_search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    keyword: Optional[str] = None,
    model_name: Optional[str] = None,
    min_rounds: Optional[int] = None,
    max_rounds: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatSession).join(User, ChatSession.user_id == User.id)
    count_query = select(func.count(ChatSession.id)).join(User, ChatSession.user_id == User.id)

    if user_search:
        user_filter = or_(
            User.nickname.like(f"%{user_search}%"),
            User.phone.like(f"%{user_search}%"),
        )
        query = query.where(user_filter)
        count_query = count_query.where(user_filter)

    if start_date:
        query = query.where(ChatSession.created_at >= start_date)
        count_query = count_query.where(ChatSession.created_at >= start_date)

    if end_date:
        query = query.where(ChatSession.created_at <= end_date)
        count_query = count_query.where(ChatSession.created_at <= end_date)

    if model_name:
        query = query.where(ChatSession.model_name == model_name)
        count_query = count_query.where(ChatSession.model_name == model_name)

    if min_rounds is not None:
        query = query.where(ChatSession.message_count >= min_rounds)
        count_query = count_query.where(ChatSession.message_count >= min_rounds)

    if max_rounds is not None:
        query = query.where(ChatSession.message_count <= max_rounds)
        count_query = count_query.where(ChatSession.message_count <= max_rounds)

    if keyword:
        sub = select(ChatMessage.session_id).where(
            ChatMessage.content.like(f"%{keyword}%")
        ).distinct()
        query = query.where(ChatSession.id.in_(sub))
        count_query = count_query.where(ChatSession.id.in_(sub))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.options(selectinload(ChatSession.user))
        .order_by(ChatSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        first_msg_result = await db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.session_id == s.id, ChatMessage.role == MessageRole.user)
            .order_by(ChatMessage.created_at.asc())
            .limit(1)
        )
        first_msg = first_msg_result.scalar_one_or_none()

        items.append(AdminChatSessionItem(
            id=s.id,
            user_id=s.user_id,
            user_nickname=s.user.nickname if s.user else None,
            user_avatar=s.user.avatar if s.user else None,
            session_type=s.session_type.value if hasattr(s.session_type, "value") else s.session_type,
            title=s.title,
            first_message=first_msg[:30] if first_msg else None,
            message_count=s.message_count or 0,
            model_name=s.model_name,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/api/admin/chat-sessions/{session_id}")
async def admin_get_session_detail(
    session_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.user), selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    messages = [
        AdminChatMessageItem(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            message_type=m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            file_url=m.file_url,
            image_urls=m.image_urls,
            file_urls=m.file_urls,
            response_time_ms=m.response_time_ms,
            prompt_tokens=m.prompt_tokens,
            completion_tokens=m.completion_tokens,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    return AdminChatSessionDetail(
        id=session.id,
        user_id=session.user_id,
        user_nickname=session.user.nickname if session.user else None,
        user_avatar=session.user.avatar if session.user else None,
        session_type=session.session_type.value if hasattr(session.session_type, "value") else session.session_type,
        title=session.title,
        model_name=session.model_name,
        message_count=session.message_count or 0,
        device_info=session.device_info,
        ip_address=session.ip_address,
        ip_location=session.ip_location,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=messages,
    )


@router.get("/api/admin/chat-sessions/{session_id}/export")
async def admin_export_session(
    session_id: int,
    format: str = Query("xlsx", regex="^(xlsx|csv)$"),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.user), selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    rows = []
    for m in session.messages:
        rows.append({
            "角色": m.role.value if hasattr(m.role, "value") else m.role,
            "内容": m.content,
            "消息类型": m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            "回复耗时(ms)": m.response_time_ms or "",
            "Prompt Tokens": m.prompt_tokens or "",
            "Completion Tokens": m.completion_tokens or "",
            "时间": str(m.created_at) if m.created_at else "",
        })

    if format == "csv":
        import csv

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        content_bytes = output.getvalue().encode("utf-8-sig")
        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="chat_{session_id}.csv"'},
        )

    # xlsx
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器未安装openpyxl，无法导出xlsx格式")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "对话记录"
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row[h] for h in headers])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="chat_{session_id}.xlsx"'},
    )


# ──────────────── 用户端 API ────────────────


@router.get("/api/chat-sessions", response_model=list)
async def user_list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id, ChatSession.is_deleted == False)
        .order_by(ChatSession.is_pinned.desc(), ChatSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    return [
        UserChatSessionItem(
            id=s.id,
            session_type=s.session_type.value if hasattr(s.session_type, "value") else s.session_type,
            title=s.title,
            message_count=s.message_count or 0,
            is_pinned=s.is_pinned or False,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get("/api/chat-sessions/{session_id}")
async def user_get_session_detail(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    messages = [
        {
            "id": m.id,
            "role": m.role.value if hasattr(m.role, "value") else m.role,
            "content": m.content,
            "message_type": m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            "file_url": m.file_url,
            "image_urls": m.image_urls,
            "file_urls": m.file_urls,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in session.messages
    ]

    return {
        "id": session.id,
        "session_type": session.session_type.value if hasattr(session.session_type, "value") else session.session_type,
        "title": session.title,
        "message_count": session.message_count or 0,
        "is_pinned": session.is_pinned or False,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "messages": messages,
    }


@router.put("/api/chat-sessions/{session_id}")
async def user_update_session(
    session_id: int,
    data: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    session.title = data.title
    await db.flush()
    await db.refresh(session)
    return {"message": "更新成功", "title": session.title}


@router.put("/api/chat-sessions/{session_id}/pin")
async def user_pin_session(
    session_id: int,
    data: ChatSessionPinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    session.is_pinned = data.is_pinned
    await db.flush()
    return {"message": "操作成功", "is_pinned": session.is_pinned}


@router.delete("/api/chat-sessions/{session_id}")
async def user_delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    session.is_deleted = True
    await db.flush()
    return {"message": "删除成功"}


@router.post("/api/chat-sessions/{session_id}/share")
async def user_share_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.is_deleted == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="对话不存在")

    if not session.share_token:
        session.share_token = uuid.uuid4().hex
        await db.flush()

    return {
        "share_token": session.share_token,
        "share_url": f"/api/shared/chat/{session.share_token}",
    }


# ──────────────── 分享页 API (公开) ────────────────


@router.get("/api/shared/chat/{share_token}")
async def get_shared_chat(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.share_token == share_token, ChatSession.is_deleted == False)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="分享链接不存在或已失效")

    messages = [
        SharedChatMessageItem(
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            message_type=m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            file_url=m.file_url,
            image_urls=m.image_urls,
            file_urls=m.file_urls,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    return SharedChatResponse(
        title=session.title,
        session_type=session.session_type.value if hasattr(session.session_type, "value") else session.session_type,
        message_count=session.message_count or 0,
        created_at=session.created_at,
        messages=messages,
    )
