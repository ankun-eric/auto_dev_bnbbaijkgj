from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import SystemMessage, User
from app.schemas.messages import (
    MessageListResponse,
    SystemMessageResponse,
    UnreadCountResponse,
)

router = APIRouter(tags=["系统消息"])


@router.get("/api/messages", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    message_type: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conditions = [SystemMessage.recipient_user_id == current_user.id]
    if message_type:
        conditions.append(SystemMessage.message_type == message_type)

    total_result = await db.execute(
        select(func.count(SystemMessage.id)).where(*conditions)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(SystemMessage)
        .where(*conditions)
        .order_by(SystemMessage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = result.scalars().all()

    items = []
    for msg in messages:
        sender_nickname = None
        if msg.sender_user_id:
            sender_result = await db.execute(
                select(User.nickname).where(User.id == msg.sender_user_id)
            )
            sender_nickname = sender_result.scalar()

        items.append(
            SystemMessageResponse(
                id=msg.id,
                message_type=msg.message_type,
                recipient_user_id=msg.recipient_user_id,
                sender_user_id=msg.sender_user_id,
                sender_nickname=sender_nickname,
                title=msg.title,
                content=msg.content,
                related_business_id=msg.related_business_id,
                related_business_type=msg.related_business_type,
                click_action=msg.click_action,
                click_action_params=msg.click_action_params,
                is_read=msg.is_read,
                read_at=msg.read_at,
                created_at=msg.created_at,
            )
        )

    return MessageListResponse(items=items, total=total, page=page, page_size=page_size)


@router.put("/api/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemMessage).where(
            SystemMessage.id == message_id,
            SystemMessage.recipient_user_id == current_user.id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")

    if not msg.is_read:
        msg.is_read = True
        msg.read_at = datetime.utcnow()
        await db.flush()

    return {"message": "已标记为已读"}


@router.put("/api/messages/read-all")
async def mark_all_messages_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(SystemMessage)
        .where(
            SystemMessage.recipient_user_id == current_user.id,
            SystemMessage.is_read == False,
        )
        .values(is_read=True, read_at=datetime.utcnow())
    )
    await db.flush()
    return {"message": "已全部标记为已读"}


@router.get("/api/messages/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(SystemMessage.id)).where(
            SystemMessage.recipient_user_id == current_user.id,
            SystemMessage.is_read == False,
        )
    )
    count = result.scalar() or 0
    return UnreadCountResponse(unread_count=count)
