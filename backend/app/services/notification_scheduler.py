import logging
from datetime import datetime, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.models import (
    HealthCheckInItem,
    MedicationCheckIn,
    MedicationReminder,
    MerchantNotification,
    NotificationLog,
    HealthCheckInRecord,
    OrderItem,
    SystemConfig,
    UnifiedOrder,
    UnifiedOrderStatus,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def check_medication_reminders():
    """Scan active medication reminders and create pending notifications for due items."""
    now = datetime.utcnow()
    current_time = now.strftime("%H:%M")
    today = date.today()

    async with async_session() as session:
        try:
            result = await session.execute(
                select(MedicationReminder).where(
                    MedicationReminder.status == "active",
                    MedicationReminder.is_paused == False,
                    MedicationReminder.remind_time.isnot(None),
                    MedicationReminder.remind_time <= current_time,
                )
            )
            reminders = result.scalars().all()

            for reminder in reminders:
                existing_checkin = await session.execute(
                    select(MedicationCheckIn).where(
                        MedicationCheckIn.reminder_id == reminder.id,
                        MedicationCheckIn.user_id == reminder.user_id,
                        MedicationCheckIn.check_in_date == today,
                    )
                )
                if existing_checkin.scalar_one_or_none():
                    continue

                existing_notification = await session.execute(
                    select(NotificationLog).where(
                        NotificationLog.user_id == reminder.user_id,
                        NotificationLog.source_type == "medication_reminder",
                        NotificationLog.source_id == reminder.id,
                        NotificationLog.created_at >= datetime.combine(today, datetime.min.time()),
                    )
                )
                if existing_notification.scalar_one_or_none():
                    continue

                notification = NotificationLog(
                    user_id=reminder.user_id,
                    source_type="medication_reminder",
                    source_id=reminder.id,
                    title="用药提醒",
                    content=f"该吃药了: {reminder.medicine_name}" + (f" ({reminder.dosage})" if reminder.dosage else ""),
                    status="pending",
                    scheduled_time=now,
                )
                session.add(notification)

            await session.commit()
            logger.info("Medication reminder check completed, time=%s", current_time)
        except Exception:
            await session.rollback()
            logger.exception("Error checking medication reminders")


async def check_checkin_reminders():
    """Scan active health check-in items and create pending notifications for due items."""
    now = datetime.utcnow()
    current_time = now.strftime("%H:%M")
    today = date.today()

    async with async_session() as session:
        try:
            result = await session.execute(
                select(HealthCheckInItem).where(
                    HealthCheckInItem.status == "active",
                    HealthCheckInItem.remind_times.isnot(None),
                )
            )
            items = result.scalars().all()

            for item in items:
                remind_times = item.remind_times or []
                if not isinstance(remind_times, list):
                    continue

                should_remind = any(t <= current_time for t in remind_times if isinstance(t, str))
                if not should_remind:
                    continue

                existing_record = await session.execute(
                    select(HealthCheckInRecord).where(
                        HealthCheckInRecord.item_id == item.id,
                        HealthCheckInRecord.user_id == item.user_id,
                        HealthCheckInRecord.check_in_date == today,
                        HealthCheckInRecord.is_completed == True,
                    )
                )
                if existing_record.scalar_one_or_none():
                    continue

                existing_notification = await session.execute(
                    select(NotificationLog).where(
                        NotificationLog.user_id == item.user_id,
                        NotificationLog.source_type == "checkin_reminder",
                        NotificationLog.source_id == item.id,
                        NotificationLog.created_at >= datetime.combine(today, datetime.min.time()),
                    )
                )
                if existing_notification.scalar_one_or_none():
                    continue

                notification = NotificationLog(
                    user_id=item.user_id,
                    source_type="checkin_reminder",
                    source_id=item.id,
                    title="健康打卡提醒",
                    content=f"别忘了完成今日打卡: {item.name}",
                    status="pending",
                    scheduled_time=now,
                )
                session.add(notification)

            await session.commit()
            logger.info("Checkin reminder check completed, time=%s", current_time)
        except Exception:
            await session.rollback()
            logger.exception("Error checking checkin reminders")


async def check_unpaid_order_timeout():
    """[订单核销码状态与未支付超时治理 v1.0] 路径 3-NEW

    替换原"门店超时未确认自动取消"逻辑。

    业务语义：
    - 触发前提：订单 status = pending_payment 且 paid_at IS NULL（即客户尚未支付）
    - 触发时长：全局 settings.PAYMENT_TIMEOUT_MINUTES（默认 15 分钟）
    - 业务结果：自动取消订单 + 同步把所有 OrderItem.redemption_code_status 置为 expired

    与已下线的"门店超时未确认自动取消"逻辑相比：
    - 本系统是自营模式（资金进入平台账户而非商家），不存在"商家不接单 → 资金兜底退款"的诉求
    - 客户已支付订单可走"申请退款 → admin 审批"链路安全拿回资金
    - 取消未支付订单是为了释放容量、清理订单表脏数据
    """
    from app.core.config import settings
    from app.services.order_cancel import cancel_order_with_items

    now = datetime.utcnow()
    timeout_minutes = int(getattr(settings, "PAYMENT_TIMEOUT_MINUTES", 15) or 15)
    timeout_threshold = now - timedelta(minutes=timeout_minutes)

    async with async_session() as session:
        try:
            from sqlalchemy.orm import selectinload

            pending_orders = await session.execute(
                select(UnifiedOrder)
                .options(selectinload(UnifiedOrder.items))
                .where(
                    UnifiedOrder.status == UnifiedOrderStatus.pending_payment,
                    UnifiedOrder.paid_at.is_(None),
                    UnifiedOrder.created_at <= timeout_threshold,
                )
            )

            cancel_count = 0
            for order in pending_orders.scalars().all():
                await cancel_order_with_items(
                    session, order,
                    cancel_reason="未支付超时自动取消",
                    cancelled_at=now,
                )
                cancel_count += 1
                logger.info(
                    "订单 %s 未支付超时（>%d 分钟），已自动取消",
                    order.order_no, timeout_minutes,
                )

            await session.commit()
            logger.info(
                "Unpaid order timeout check completed, cancelled=%d, threshold=%d min",
                cancel_count, timeout_minutes,
            )
        except Exception:
            await session.rollback()
            logger.exception("Error checking unpaid order timeout")


async def check_appointment_reminders():
    """Send reminders for upcoming appointments based on configured advance hours."""
    now = datetime.utcnow()

    async with async_session() as session:
        try:
            cfg_result = await session.execute(
                select(SystemConfig).where(
                    SystemConfig.config_key == "appointment_reminder_advance_hours"
                )
            )
            cfg = cfg_result.scalar_one_or_none()
            advance_hours = int(cfg.config_value) if cfg else 24

            remind_threshold = now + timedelta(hours=advance_hours)

            upcoming = await session.execute(
                select(OrderItem, UnifiedOrder)
                .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
                .where(
                    OrderItem.appointment_time.isnot(None),
                    OrderItem.appointment_time > now,
                    OrderItem.appointment_time <= remind_threshold,
                    UnifiedOrder.status.in_([
                        UnifiedOrderStatus.pending_use,
                        UnifiedOrderStatus.pending_shipment,
                    ]),
                )
            )

            from app.models.models import Notification, NotificationType

            for oi, order in upcoming.all():
                existing = await session.execute(
                    select(Notification).where(
                        Notification.user_id == order.user_id,
                        Notification.title == "预约提醒",
                        Notification.created_at >= now - timedelta(hours=advance_hours),
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                appt_time_str = oi.appointment_time.strftime("%Y-%m-%d %H:%M") if oi.appointment_time else ""
                session.add(Notification(
                    user_id=order.user_id,
                    title="预约提醒",
                    content=f"您的预约 {oi.product_name} 将于 {appt_time_str} 开始，请准时到店。",
                    type=NotificationType.order,
                ))

            await session.commit()
            logger.info("Appointment reminder check completed")
        except Exception:
            await session.rollback()
            logger.exception("Error checking appointment reminders")


async def check_order_upcoming_one_hour():
    """[订单系统增强 PRD v1.0 F7/R12] 服务时段开始前 1 小时触发站内信，每 5 分钟扫描一次。

    扫描规则：在 [now+55min, now+65min] 区间内开始的预约订单。
    通过 Notification.event_type='order_upcoming' + order_id 唯一性去重。
    """
    now = datetime.utcnow()
    window_start = now + timedelta(minutes=55)
    window_end = now + timedelta(minutes=65)

    async with async_session() as session:
        try:
            from app.models.models import Notification

            upcoming = await session.execute(
                select(OrderItem, UnifiedOrder)
                .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
                .where(
                    OrderItem.appointment_time.isnot(None),
                    OrderItem.appointment_time >= window_start,
                    OrderItem.appointment_time <= window_end,
                    UnifiedOrder.status.in_([
                        UnifiedOrderStatus.pending_use,
                        UnifiedOrderStatus.appointed,
                        UnifiedOrderStatus.partial_used,
                    ]),
                )
            )

            for oi, order in upcoming.all():
                # 去重：该订单已有 order_upcoming 类型的通知就跳过
                exists = await session.execute(
                    select(Notification.id).where(
                        Notification.user_id == order.user_id,
                        Notification.order_id == order.id,
                        Notification.event_type == "order_upcoming",
                    )
                )
                if exists.scalar_one_or_none():
                    continue

                from app.services.order_notification import notify_order_upcoming
                await notify_order_upcoming(
                    session,
                    user_id=order.user_id,
                    order_id=order.id,
                    order_no=order.order_no,
                    appointment_time=oi.appointment_time,
                )

            await session.commit()
            logger.info("Order upcoming-1h check completed")
        except Exception:
            await session.rollback()
            logger.exception("Error checking order upcoming-1h")


def init_scheduler():
    """Initialize and start the APScheduler."""
    scheduler.add_job(
        check_medication_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="check_medication_reminders",
        replace_existing=True,
    )
    # [订单系统增强 PRD v1.0 F7/R12] 服务前 1 小时提醒，每 5 分钟扫描一次
    scheduler.add_job(
        check_order_upcoming_one_hour,
        trigger=IntervalTrigger(minutes=5),
        id="check_order_upcoming_one_hour",
        replace_existing=True,
    )
    scheduler.add_job(
        check_checkin_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="check_checkin_reminders",
        replace_existing=True,
    )
    # [订单核销码状态与未支付超时治理 v1.0] 路径 3-NEW
    # 替换原"门店超时未确认自动取消"为"未支付超时自动取消"
    scheduler.add_job(
        check_unpaid_order_timeout,
        trigger=IntervalTrigger(minutes=1),
        id="check_unpaid_order_timeout",
        replace_existing=True,
    )
    scheduler.add_job(
        check_appointment_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="check_appointment_reminders",
        replace_existing=True,
    )

    # ───── [PRD 订单状态机简化方案 v1.0] 订单状态推进 + 提醒任务 ─────
    # R1（appointed → pending_use 翻转）已下线：现在用户首次填预约日就直接 pending_use。
    # 仅保留 R2（次日 00:00 退回未核销订单到 pending_appointment）+ 提醒任务（含 T-1 18:00 新节点）。
    from app.tasks.order_status_auto_progress import (
        run_appointment_reminders_v2,
        run_r2_flip_back_to_appointment,
    )
    # R2：每分钟扫描一次；逻辑上仅在次日 00:00+ 退回未核销订单
    scheduler.add_job(
        run_r2_flip_back_to_appointment,
        trigger=IntervalTrigger(minutes=1),
        id="order_r2_flip_back_to_appointment",
        replace_existing=True,
    )
    # 提醒节点：每分钟扫一次，节点内部用窗口 + NotificationLog 去重
    # 含新增「T-1 18:00 到店提醒」+ 老 5 个节点（已自动 join statuses 改为 pending_use）
    scheduler.add_job(
        run_appointment_reminders_v2,
        trigger=IntervalTrigger(minutes=1),
        id="order_appointment_reminders_v2",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Notification scheduler started")


def shutdown_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Notification scheduler stopped")
