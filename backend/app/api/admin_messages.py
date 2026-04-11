from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import SystemMessage, User
from app.schemas.messages import (
    AdminMessageCreate,
    AdminMessageStatsResponse,
    SystemMessageResponse,
)

router = APIRouter(tags=["管理端-系统消息"])

admin_dep = require_role("admin")


@router.get("/api/admin/messages")
async def admin_list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    message_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user_search: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if message_type:
        conditions.append(SystemMessage.message_type == message_type)
    if is_read is not None:
        conditions.append(SystemMessage.is_read == is_read)
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date)
            conditions.append(SystemMessage.created_at >= dt)
        except ValueError:
            pass
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date)
            conditions.append(SystemMessage.created_at <= dt)
        except ValueError:
            pass

    if user_search:
        user_ids_result = await db.execute(
            select(User.id).where(
                or_(
                    User.nickname.contains(user_search),
                    User.phone.contains(user_search),
                )
            )
        )
        user_ids = [uid for uid in user_ids_result.scalars().all()]
        if user_ids:
            conditions.append(SystemMessage.recipient_user_id.in_(user_ids))
        else:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    total_result = await db.execute(
        select(func.count(SystemMessage.id)).where(*conditions) if conditions
        else select(func.count(SystemMessage.id))
    )
    total = total_result.scalar() or 0

    query = select(SystemMessage)
    if conditions:
        query = query.where(*conditions)
    query = query.order_by(SystemMessage.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    messages = result.scalars().all()

    items = []
    for msg in messages:
        sender_nickname = None
        if msg.sender_user_id:
            sender_result = await db.execute(
                select(User.nickname).where(User.id == msg.sender_user_id)
            )
            sender_nickname = sender_result.scalar()

        recipient_result = await db.execute(
            select(User).where(User.id == msg.recipient_user_id)
        )
        recipient = recipient_result.scalar_one_or_none()

        items.append({
            "id": msg.id,
            "message_type": msg.message_type,
            "recipient_user_id": msg.recipient_user_id,
            "recipient_nickname": recipient.nickname if recipient else None,
            "recipient_phone": recipient.phone if recipient else None,
            "sender_user_id": msg.sender_user_id,
            "sender_nickname": sender_nickname,
            "title": msg.title,
            "content": msg.content,
            "related_business_id": msg.related_business_id,
            "related_business_type": msg.related_business_type,
            "click_action": msg.click_action,
            "click_action_params": msg.click_action_params,
            "is_read": msg.is_read,
            "read_at": msg.read_at.isoformat() if msg.read_at else None,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/api/admin/messages")
async def admin_send_message(
    data: AdminMessageCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if not data.recipient_user_ids:
        raise HTTPException(status_code=400, detail="接收人列表不能为空")

    created_ids = []
    for user_id in data.recipient_user_ids:
        user_result = await db.execute(select(User).where(User.id == user_id))
        if not user_result.scalar_one_or_none():
            continue

        msg = SystemMessage(
            message_type=data.message_type,
            recipient_user_id=user_id,
            sender_user_id=current_user.id,
            title=data.title,
            content=data.content,
        )
        db.add(msg)
        await db.flush()
        created_ids.append(msg.id)

    return {"message": f"已发送 {len(created_ids)} 条消息", "created_ids": created_ids}


@router.get("/api/admin/messages/stats")
async def admin_message_stats(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(SystemMessage.id)))
    total = total_result.scalar() or 0

    unread_result = await db.execute(
        select(func.count(SystemMessage.id)).where(SystemMessage.is_read == False)
    )
    unread = unread_result.scalar() or 0

    type_result = await db.execute(
        select(SystemMessage.message_type, func.count(SystemMessage.id))
        .group_by(SystemMessage.message_type)
    )
    type_counts = {row[0]: row[1] for row in type_result.all()}

    return AdminMessageStatsResponse(total=total, unread=unread, type_counts=type_counts)


@router.get("/api/admin/messages/{message_id}")
async def admin_get_message_detail(
    message_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemMessage).where(SystemMessage.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")

    sender_nickname = None
    if msg.sender_user_id:
        sender_result = await db.execute(
            select(User.nickname).where(User.id == msg.sender_user_id)
        )
        sender_nickname = sender_result.scalar()

    recipient_result = await db.execute(
        select(User).where(User.id == msg.recipient_user_id)
    )
    recipient = recipient_result.scalar_one_or_none()

    return {
        "id": msg.id,
        "message_type": msg.message_type,
        "recipient_user_id": msg.recipient_user_id,
        "recipient_nickname": recipient.nickname if recipient else None,
        "recipient_phone": recipient.phone if recipient else None,
        "sender_user_id": msg.sender_user_id,
        "sender_nickname": sender_nickname,
        "title": msg.title,
        "content": msg.content,
        "related_business_id": msg.related_business_id,
        "related_business_type": msg.related_business_type,
        "click_action": msg.click_action,
        "click_action_params": msg.click_action_params,
        "is_read": msg.is_read,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }
