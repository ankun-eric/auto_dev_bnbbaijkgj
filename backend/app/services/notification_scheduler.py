import logging
from datetime import datetime, date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.core.database import async_session
from app.models.models import (
    HealthCheckInItem,
    MedicationCheckIn,
    MedicationReminder,
    NotificationLog,
    HealthCheckInRecord,
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
    scheduler.start()
    logger.info("Notification scheduler started")


def shutdown_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Notification scheduler stopped")
