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


async def _get_timeout_config(session: AsyncSession) -> dict:
    keys = ["order_urge_minutes", "order_timeout_minutes", "order_timeout_action"]
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(keys))
    )
    cfg = {c.config_key: c.config_value for c in result.scalars().all()}
    return {
        "urge_minutes": int(cfg.get("order_urge_minutes", "30")),
        "timeout_minutes": int(cfg.get("order_timeout_minutes", "60")),
        "timeout_action": cfg.get("order_timeout_action", "auto_cancel"),
    }


async def check_order_confirm_timeout():
    """Check for orders that haven't been confirmed by store within timeout policy."""
    now = datetime.utcnow()

    async with async_session() as session:
        try:
            cfg = await _get_timeout_config(session)
            urge_minutes = cfg["urge_minutes"]
            timeout_minutes = cfg["timeout_minutes"]
            timeout_action = cfg["timeout_action"]

            urge_threshold = now - timedelta(minutes=urge_minutes)
            timeout_threshold = now - timedelta(minutes=timeout_minutes)

            pending_orders = await session.execute(
                select(UnifiedOrder).where(
                    UnifiedOrder.store_confirmed == False,
                    UnifiedOrder.store_id.isnot(None),
                    UnifiedOrder.status.in_([
                        UnifiedOrderStatus.pending_use,
                        UnifiedOrderStatus.pending_shipment,
                    ]),
                    UnifiedOrder.paid_at.isnot(None),
                )
            )

            for order in pending_orders.scalars().all():
                paid_at = order.paid_at
                if not paid_at:
                    continue

                if paid_at <= timeout_threshold:
                    if timeout_action == "auto_cancel":
                        order.status = UnifiedOrderStatus.cancelled
                        order.cancelled_at = now
                        order.cancel_reason = "门店超时未确认，系统自动取消"
                        order.updated_at = now
                        logger.info("订单 %s 超时未确认，已自动取消", order.order_no)

                    if order.store_id:
                        session.add(MerchantNotification(
                            user_id=order.user_id,
                            store_id=order.store_id,
                            title="订单超时未确认",
                            content=f"订单 {order.order_no} 已超时未确认",
                            notification_type="order",
                        ))

                elif paid_at <= urge_threshold:
                    existing = await session.execute(
                        select(MerchantNotification).where(
                            MerchantNotification.store_id == order.store_id,
                            MerchantNotification.title == "订单待确认催促",
                            MerchantNotification.created_at >= paid_at,
                        )
                    )
                    if not existing.scalar_one_or_none() and order.store_id:
                        from app.models.models import MerchantStoreMembership
                        staff_result = await session.execute(
                            select(MerchantStoreMembership.user_id).where(
                                MerchantStoreMembership.store_id == order.store_id,
                                MerchantStoreMembership.status == "active",
                            )
                        )
                        for (uid,) in staff_result.all():
                            session.add(MerchantNotification(
                                user_id=uid,
                                store_id=order.store_id,
                                title="订单待确认催促",
                                content=f"订单 {order.order_no} 待确认，请尽快处理",
                                notification_type="order",
                            ))

            await session.commit()
            logger.info("Order confirm timeout check completed")
        except Exception:
            await session.rollback()
            logger.exception("Error checking order confirm timeout")


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


def init_scheduler():
    """Initialize and start the APScheduler."""
    scheduler.add_job(
        check_medication_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="check_medication_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        check_checkin_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="check_checkin_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        check_order_confirm_timeout,
        trigger=IntervalTrigger(minutes=1),
        id="check_order_confirm_timeout",
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
