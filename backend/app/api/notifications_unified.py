"""
PRD-425：AI 对话首页顶栏未读数徽标——统一聚合接口。

提供 GET /api/v1/notifications/unread-count，
返回站内通知中心**所有分类**的未读总数（系统消息 + 业务通知 + 公告等）。

设计要点：
- 累加 SystemMessage + Notification 两张表中当前用户未读消息数量
- 对未登录或异常情况返回 0（前端按 PRD 异常兜底逻辑：徽标不显示 / 显示 0 红点）
- 该接口为只读，不修改任何数据
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Notification, SystemMessage, User

router = APIRouter(prefix="/api/v1/notifications", tags=["通知中心-统一聚合"])


@router.get("/unread-count")
async def get_total_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户在站内通知中心**所有分类**的未读总数。

    返回结构（兼容 PRD §6.2.1）：
    {
        "code": 0,
        "msg": "ok",
        "data": {
            "unreadCount": 5
        }
    }
    """
    # 1. 系统消息（公告、系统通知）
    sys_res = await db.execute(
        select(func.count(SystemMessage.id)).where(
            SystemMessage.recipient_user_id == current_user.id,
            SystemMessage.is_read == False,  # noqa: E712
        )
    )
    sys_unread = int(sys_res.scalar() or 0)

    # 2. 业务通知（订单、健康提醒等）
    notif_res = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    notif_unread = int(notif_res.scalar() or 0)

    total = sys_unread + notif_unread

    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "unreadCount": total,
            "breakdown": {
                "system_messages": sys_unread,
                "notifications": notif_unread,
            },
        },
    }
