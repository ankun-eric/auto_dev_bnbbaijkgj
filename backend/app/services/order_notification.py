"""[订单系统增强 PRD v1.0] 订单事件 → 站内消息触发器。

本服务封装 4 类事件的统一入口：
1. 订单状态变更（order_status_changed）
2. 商家上传附件（order_attachment_added）
3. 临近服务提醒（order_upcoming，由定时任务调用）
4. 客户操作回执（order_created / order_paid / order_cancelled）

设计原则：
- 单条事件 → 单条 Notification 记录，仅按订单粒度做红点
- 失败不阻塞主业务（捕获异常打日志）
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Notification, NotificationType

logger = logging.getLogger(__name__)


_STATUS_CHINESE = {
    "pending_payment": "待付款",
    "pending_shipment": "待发货",
    "pending_receipt": "待收货",
    "pending_appointment": "待预约",
    "appointed": "已预约",
    "pending_use": "待核销",
    "partial_used": "部分核销",
    "pending_review": "待评价",
    "completed": "已完成",
    "expired": "已过期",
    "refunding": "退款中",
    "refunded": "已退款",
    "cancelled": "已取消",
}


async def _create_notification(
    db: AsyncSession,
    *,
    user_id: int,
    order_id: Optional[int],
    event_type: str,
    title: str,
    content: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> Optional[Notification]:
    """通用站内消息写入入口。失败仅记录日志，不抛异常。"""
    try:
        n = Notification(
            user_id=user_id,
            order_id=order_id,
            event_type=event_type,
            title=title,
            content=content,
            type=NotificationType.order,
            is_read=False,
            extra_data=extra_data or {},
        )
        db.add(n)
        await db.flush()
        return n
    except Exception as e:  # noqa: BLE001
        logger.warning("notification create failed (event=%s order=%s user=%s): %s",
                       event_type, order_id, user_id, e)
        return None


async def notify_order_status_changed(
    db: AsyncSession,
    *,
    user_id: int,
    order_id: int,
    order_no: str,
    new_status: str,
) -> None:
    if new_status not in _STATUS_CHINESE:
        return
    cn = _STATUS_CHINESE.get(new_status, new_status)
    await _create_notification(
        db,
        user_id=user_id,
        order_id=order_id,
        event_type="order_status_changed",
        title=f"订单状态已变更为「{cn}」",
        content=f"您的订单 #{order_no} 已变更为「{cn}」",
        extra_data={"order_no": order_no, "new_status": new_status},
    )


async def notify_attachment_added(
    db: AsyncSession,
    *,
    user_id: int,
    order_id: int,
    order_no: str,
    attachment_count: int = 1,
) -> None:
    await _create_notification(
        db,
        user_id=user_id,
        order_id=order_id,
        event_type="order_attachment_added",
        title="商家上传了服务凭证",
        content=f"商家已为订单 #{order_no} 上传了 {attachment_count} 个服务凭证，点击查看",
        extra_data={"order_no": order_no, "attachment_count": attachment_count},
    )


async def notify_order_upcoming(
    db: AsyncSession,
    *,
    user_id: int,
    order_id: int,
    order_no: str,
    appointment_time: datetime,
) -> None:
    time_str = appointment_time.strftime("%H:%M")
    await _create_notification(
        db,
        user_id=user_id,
        order_id=order_id,
        event_type="order_upcoming",
        title="您的服务即将开始",
        content=f"您预约的服务将于 1 小时后开始（{time_str}），请准时到达",
        extra_data={"order_no": order_no, "appointment_time": appointment_time.isoformat()},
    )


async def notify_order_created(
    db: AsyncSession,
    *,
    user_id: int,
    order_id: int,
    order_no: str,
) -> None:
    await _create_notification(
        db,
        user_id=user_id,
        order_id=order_id,
        event_type="order_created",
        title="下单成功",
        content=f"订单 #{order_no} 已下单成功，等待支付",
        extra_data={"order_no": order_no},
    )


async def notify_order_paid(
    db: AsyncSession,
    *,
    user_id: int,
    order_id: int,
    order_no: str,
) -> None:
    await _create_notification(
        db,
        user_id=user_id,
        order_id=order_id,
        event_type="order_paid",
        title="付款成功",
        content=f"订单 #{order_no} 付款成功",
        extra_data={"order_no": order_no},
    )


async def notify_order_cancelled(
    db: AsyncSession,
    *,
    user_id: int,
    order_id: int,
    order_no: str,
) -> None:
    await _create_notification(
        db,
        user_id=user_id,
        order_id=order_id,
        event_type="order_cancelled",
        title="订单已取消",
        content=f"订单 #{order_no} 已取消成功",
        extra_data={"order_no": order_no},
    )
