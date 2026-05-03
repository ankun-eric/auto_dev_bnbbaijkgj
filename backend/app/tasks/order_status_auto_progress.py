"""订单状态自动推进任务（PRD「订单状态自动推进策略」v1.0）

实现两条核心规则：
- R1: 预约日 00:00 全量翻转「已预约 appointed」→「待核销 pending_use」
- R2: 次日 00:00 兜底将未核销「待核销 pending_use」→「已预约 appointed」回退到「待预约 awaiting_appointment」
       （在系统中体现为：清空 OrderItem.appointment_time、订单 status 回到 pending_appointment）

兼顾的提醒推送节点（按 PRD 2.4 节，以 OrderItem.appointment_time 为锚点）：
- 预约日前一天 21:00：明日预约提醒
- 预约时刻前 30 分钟：临近赴约提醒
- 预约时刻 +30 分钟：商家在等您
- 预约时刻 +2 小时：是否需要改约
- 次日 09:00：未到店重新预约提醒

实现要点：
1. 状态翻转 + 通知入库放在同一事务中，避免不一致
2. 每个推送节点借助 NotificationLog 去重，幂等可重放
3. 提供 `lazy_progress_order` 给 unified_orders 接口侧调用，作为定时器漏跑的实时兜底
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, time as dtime
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session
from app.models.models import (
    Notification,
    NotificationLog,
    NotificationType,
    OrderItem,
    UnifiedOrder,
    UnifiedOrderStatus,
)


logger = logging.getLogger(__name__)


# ──────────────── R1 / R2 状态翻转 ────────────────


async def run_r1_flip_to_pending_use(session: Optional[AsyncSession] = None) -> int:
    """R1：预约日 00:00 翻转。

    将所有 status=appointed 且 OrderItem.appointment_time 的日期 <= 今天的订单
    翻为 pending_use。返回受影响订单数。
    """
    own_session = session is None
    if own_session:
        session = async_session()  # type: ignore[assignment]
    try:
        if own_session:
            ctx = session  # type: ignore[assignment]
            await ctx.__aenter__()  # type: ignore[union-attr]
        affected = await _do_r1(session)  # type: ignore[arg-type]
        if own_session:
            await session.commit()  # type: ignore[union-attr]
        return affected
    except Exception:
        if own_session:
            await session.rollback()  # type: ignore[union-attr]
        logger.exception("R1 flip failed")
        return 0
    finally:
        if own_session:
            try:
                await session.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass


async def _do_r1(session: AsyncSession) -> int:
    """R1 核心实现：扫描订单 + 翻状态 + 入站内消息。"""
    today_end = datetime.combine(datetime.utcnow().date(), dtime(23, 59, 59))
    rows = await session.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.status == UnifiedOrderStatus.appointed)
    )
    affected = 0
    now = datetime.utcnow()
    for order in rows.scalars().all():
        appt = _earliest_appt(order)
        if appt is None:
            continue
        if appt <= today_end:
            order.status = UnifiedOrderStatus.pending_use
            order.updated_at = now
            session.add(Notification(
                user_id=order.user_id,
                title="订单已可核销",
                content=f"您的订单 {order.order_no} 预约日已到，请在今日 24:00 前到店出示核销码。",
                type=NotificationType.order,
            ))
            affected += 1
    if affected:
        logger.info("[R1] 翻转 appointed → pending_use: %d 笔", affected)
    return affected


async def run_r2_flip_back_to_appointment(session: Optional[AsyncSession] = None) -> int:
    """R2：次日 00:00 兜底回退。

    将所有 status=pending_use 且 OrderItem.appointment_time 的日期 < 今天且未核销的订单
    清空 appointment_time、status 退回 pending_appointment。返回受影响订单数。
    """
    own_session = session is None
    if own_session:
        session = async_session()  # type: ignore[assignment]
    try:
        if own_session:
            await session.__aenter__()  # type: ignore[union-attr]
        affected = await _do_r2(session)  # type: ignore[arg-type]
        if own_session:
            await session.commit()  # type: ignore[union-attr]
        return affected
    except Exception:
        if own_session:
            await session.rollback()  # type: ignore[union-attr]
        logger.exception("R2 flip failed")
        return 0
    finally:
        if own_session:
            try:
                await session.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass


async def _do_r2(session: AsyncSession) -> int:
    """R2 核心实现：超时未核销的 pending_use 退回 pending_appointment。"""
    today_start = datetime.combine(datetime.utcnow().date(), dtime(0, 0, 0))
    rows = await session.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.status == UnifiedOrderStatus.pending_use)
    )
    affected = 0
    now = datetime.utcnow()
    for order in rows.scalars().all():
        appt = _earliest_appt(order)
        if appt is None:
            continue
        # 仅对预约日期 < 今天 且 仍未核销（used_redeem_count=0）的订单回退
        if appt < today_start:
            any_used = any(
                (it.used_redeem_count or 0) > 0 for it in order.items
            )
            if any_used:
                continue
            for it in order.items:
                it.appointment_time = None
            order.status = UnifiedOrderStatus.pending_appointment
            order.updated_at = now
            session.add(Notification(
                user_id=order.user_id,
                title="预约已重置，请重新预约",
                content=f"您的订单 {order.order_no} 昨日未到店核销，已自动退回待预约状态，请重新选择预约时间。",
                type=NotificationType.order,
            ))
            affected += 1
    if affected:
        logger.info("[R2] 退回 pending_use → pending_appointment: %d 笔", affected)
    return affected


# ──────────────── 提醒推送节点（按 PRD 2.4） ────────────────


async def run_appointment_reminders_v2() -> dict:
    """统一调度 5 个提醒节点。每分钟扫描一次，使用窗口 + NotificationLog 去重。

    Returns:
        各节点本次发送条数统计，便于运维查看。
    """
    counts = {
        "day_before_21": 0,        # 5/9 21:00：明日 10:00 有预约
        "before_30min": 0,          # 5/10 09:30：30 分钟后赴约
        "after_30min": 0,           # 5/10 10:30：商家在等您
        "after_2h": 0,              # 5/10 12:00：是否需要改约
        "next_day_9am": 0,          # 5/11 09:00：未到店重新预约
    }
    async with async_session() as session:
        try:
            counts["day_before_21"] = await _send_window(
                session,
                key="appt_day_before_21",
                title="明日预约提醒",
                statuses=[UnifiedOrderStatus.appointed],
                appt_lower=_today_at(21, 0) + timedelta(hours=13),  # 明日 10:00 起
                appt_upper=_today_at(21, 0) + timedelta(hours=37),  # 明日 24:00
                send_window_lower=_today_at(20, 55),
                send_window_upper=_today_at(21, 5),
                content_tpl="您明日 {appt} 有 1 笔预约，请准时赴约。",
            )

            counts["before_30min"] = await _send_window(
                session,
                key="appt_before_30min",
                title="临近赴约提醒",
                statuses=[UnifiedOrderStatus.pending_use, UnifiedOrderStatus.appointed],
                appt_lower=datetime.utcnow() + timedelta(minutes=25),
                appt_upper=datetime.utcnow() + timedelta(minutes=35),
                send_window_lower=datetime.utcnow() - timedelta(minutes=5),
                send_window_upper=datetime.utcnow() + timedelta(minutes=5),
                content_tpl="您 30 分钟后有预约（{appt}），建议提前出门。",
            )

            counts["after_30min"] = await _send_window(
                session,
                key="appt_after_30min",
                title="商家在等您",
                statuses=[UnifiedOrderStatus.pending_use],
                appt_lower=datetime.utcnow() - timedelta(minutes=35),
                appt_upper=datetime.utcnow() - timedelta(minutes=25),
                send_window_lower=datetime.utcnow() - timedelta(minutes=5),
                send_window_upper=datetime.utcnow() + timedelta(minutes=5),
                content_tpl="您的预约时间 {appt} 已过去 30 分钟，商家在等您，请尽快到店。",
            )

            counts["after_2h"] = await _send_window(
                session,
                key="appt_after_2h",
                title="是否需要改约",
                statuses=[UnifiedOrderStatus.pending_use],
                appt_lower=datetime.utcnow() - timedelta(hours=2, minutes=5),
                appt_upper=datetime.utcnow() - timedelta(hours=1, minutes=55),
                send_window_lower=datetime.utcnow() - timedelta(minutes=5),
                send_window_upper=datetime.utcnow() + timedelta(minutes=5),
                content_tpl="您的预约时间 {appt} 已过去 2 小时仍未到店，是否需要改约？可在订单详情中重新选择时间。",
            )

            counts["next_day_9am"] = await _send_window(
                session,
                key="appt_next_day_9am",
                title="未到店重新预约提醒",
                statuses=[UnifiedOrderStatus.pending_appointment],
                # 昨日有预约且已被 R2 清空 appointment_time 的订单 → 通过 R2 通知去补提醒
                # 此节点直接对所有 pending_appointment 且 updated_at 在昨日 23:00 ~ 今日 01:00（即 R2 刚处理过）的发
                appt_lower=None,
                appt_upper=None,
                send_window_lower=_today_at(8, 55),
                send_window_upper=_today_at(9, 5),
                content_tpl="您有 1 笔订单 {order_no} 未到店，是否重新预约？",
                use_updated_at_window=(
                    _today_at(0, 0) - timedelta(hours=1),
                    _today_at(1, 0),
                ),
            )

            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("appointment reminders v2 failed")
    if any(counts.values()):
        logger.info("[ReminderV2] sent: %s", counts)
    return counts


async def _send_window(
    session: AsyncSession,
    *,
    key: str,
    title: str,
    statuses: list,
    appt_lower: Optional[datetime],
    appt_upper: Optional[datetime],
    send_window_lower: datetime,
    send_window_upper: datetime,
    content_tpl: str,
    use_updated_at_window: Optional[tuple] = None,
) -> int:
    """发送某节点的提醒，幂等 + 时间窗口控制。

    Args:
        key: 用于 NotificationLog.source_type 的去重 key（避免一笔订单多发）
        statuses: 订单状态白名单
        appt_lower/appt_upper: OrderItem.appointment_time 的窗口（None 表示不按预约时间筛选）
        send_window_lower/upper: 当前时刻在此窗口内才发送
        content_tpl: 含 {appt}/{order_no} 占位
        use_updated_at_window: 如非 None，则附加按 UnifiedOrder.updated_at 在窗口内筛选
    """
    now = datetime.utcnow()
    if not (send_window_lower <= now <= send_window_upper):
        return 0

    base_q = select(UnifiedOrder).options(selectinload(UnifiedOrder.items))
    base_q = base_q.where(UnifiedOrder.status.in_(statuses))

    if appt_lower is not None and appt_upper is not None:
        # 通过 join OrderItem 按预约时间窗口筛选
        sub = (
            select(OrderItem.order_id)
            .where(
                OrderItem.appointment_time.isnot(None),
                OrderItem.appointment_time >= appt_lower,
                OrderItem.appointment_time <= appt_upper,
            )
            .distinct()
        )
        base_q = base_q.where(UnifiedOrder.id.in_(sub))

    if use_updated_at_window is not None:
        u_lo, u_hi = use_updated_at_window
        base_q = base_q.where(
            UnifiedOrder.updated_at >= u_lo,
            UnifiedOrder.updated_at <= u_hi,
        )

    rows = await session.execute(base_q)
    sent = 0
    for order in rows.scalars().all():
        # 去重：同一订单同一 key 当日只发一次
        today = datetime.utcnow().date()
        dup_q = await session.execute(
            select(NotificationLog).where(
                NotificationLog.user_id == order.user_id,
                NotificationLog.source_type == key,
                NotificationLog.source_id == order.id,
                NotificationLog.created_at >= datetime.combine(today, dtime.min),
            )
        )
        if dup_q.scalar_one_or_none():
            continue

        appt = _earliest_appt(order)
        appt_str = appt.strftime("%Y-%m-%d %H:%M") if appt else "您选定的时间"
        content = content_tpl.format(appt=appt_str, order_no=order.order_no)

        session.add(Notification(
            user_id=order.user_id,
            title=title,
            content=content,
            type=NotificationType.order,
        ))
        session.add(NotificationLog(
            user_id=order.user_id,
            source_type=key,
            source_id=order.id,
            title=title,
            content=content,
            status="sent",
            scheduled_time=now,
        ))
        sent += 1
    return sent


# ──────────────── 懒兜底（接口侧实时翻转） ────────────────


async def lazy_progress_order(order: UnifiedOrder, session: AsyncSession) -> bool:
    """供 unified_orders 接口侧调用：用户/商家打开详情或核销码页面时，
    根据当前时间补翻转 R1/R2，确保即使定时器漏跑也能即时感知。

    Returns:
        True 表示状态有变化（调用方需 commit）。
    """
    appt = _earliest_appt(order)
    if appt is None:
        return False
    now = datetime.utcnow()
    today_start = datetime.combine(now.date(), dtime(0, 0, 0))
    today_end = datetime.combine(now.date(), dtime(23, 59, 59))

    # R1: appointed + 预约日 <= 今天
    if order.status == UnifiedOrderStatus.appointed and appt <= today_end:
        order.status = UnifiedOrderStatus.pending_use
        order.updated_at = now
        return True

    # R2: pending_use + 预约日 < 今天 + 未核销
    if order.status == UnifiedOrderStatus.pending_use and appt < today_start:
        any_used = any(
            (it.used_redeem_count or 0) > 0 for it in (order.items or [])
        )
        if not any_used:
            for it in order.items:
                it.appointment_time = None
            order.status = UnifiedOrderStatus.pending_appointment
            order.updated_at = now
            return True
    return False


# ──────────────── 工具函数 ────────────────


def _earliest_appt(order: UnifiedOrder) -> Optional[datetime]:
    """取订单中最早的 appointment_time。"""
    times = [it.appointment_time for it in (order.items or []) if it.appointment_time]
    return min(times) if times else None


def _today_at(hour: int, minute: int) -> datetime:
    """返回今日的 hh:mm 时刻（UTC）。"""
    today = datetime.utcnow().date()
    return datetime.combine(today, dtime(hour, minute))
