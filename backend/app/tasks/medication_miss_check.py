"""[PRD-468 2026-05-12] 漏打卡代为提醒扫描任务。

- 每 10 分钟扫描一次（由 notification_scheduler 注册）
- 宽限期固定 15 分钟
- 通知对象：family_management 表中 status=active 的全部共管者
- 去重：notification_logs (user_id, source_type='medication_missed_for_managed_user', source_id={plan_id}_{date}_{HH:MM})
        每个共管者每天每个 (reminder, 时间槽) 最多 1 条
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.models import (
    FamilyManagement,
    FamilyMember,
    MedicationLog,
    MedicationPlan,
    NotificationLog,
    User,
)

logger = logging.getLogger(__name__)

GRACE_MINUTES = 15
SOURCE_TYPE = "medication_missed_for_managed_user"


async def _query_active_managers(db: AsyncSession, managed_user_id: int):
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        )
    )
    return res.scalars().all()


async def miss_check_medication_reminders() -> None:
    """[PRD-468] 漏打卡扫描入口。"""
    now = datetime.utcnow()
    today = date.today()
    grace = timedelta(minutes=GRACE_MINUTES)

    async with async_session() as db:
        try:
            # 拉所有 enabled 用药计划
            plans = (await db.execute(
                select(MedicationPlan).where(MedicationPlan.enabled == True)  # noqa: E712
            )).scalars().all()

            for plan in plans:
                schedule = list(plan.schedule or [])
                if not schedule:
                    continue
                # 计算今日已逾期未打卡的时间槽
                for t in schedule:
                    try:
                        h, m = int(t[:2]), int(t[3:])
                    except Exception:
                        continue
                    sched_dt = datetime.combine(today, datetime.min.time()).replace(hour=h, minute=m)
                    if now < sched_dt + grace:
                        continue  # 还在宽限期内

                    # 是否已打卡？
                    existing_log = (await db.execute(
                        select(MedicationLog).where(
                            MedicationLog.plan_id == plan.id,
                            MedicationLog.log_date == today,
                            MedicationLog.scheduled_time == t,
                            MedicationLog.revoked == False,  # noqa: E712
                        )
                    )).scalar_one_or_none()
                    if existing_log:
                        continue

                    source_id_key = f"{plan.id}_{today.isoformat()}_{t}"

                    # 查询该用户的 active 共管者
                    managers = await _query_active_managers(db, plan.user_id)
                    if not managers:
                        continue

                    # 取被管人昵称（用于通知文案）
                    user_row = (await db.execute(
                        select(User).where(User.id == plan.user_id)
                    )).scalar_one_or_none()
                    owner_nickname = (user_row.nickname if user_row and getattr(user_row, "nickname", None)
                                       else (user_row.phone if user_row else f"用户{plan.user_id}"))

                    for mgr in managers:
                        # 去重：同 user_id + source_type + source_id 24h 内已发过则跳过
                        # NotificationLog.source_id 是 Integer 类型，用 hash 后取模做整数去重不可靠；
                        # 改用 source_type+title+content 唯一对（保守起见用 hash 后正整数）
                        unique_int_id = abs(hash(source_id_key)) % 2_000_000_000

                        existing_notif = (await db.execute(
                            select(NotificationLog).where(
                                NotificationLog.user_id == mgr.manager_user_id,
                                NotificationLog.source_type == SOURCE_TYPE,
                                NotificationLog.source_id == unique_int_id,
                            )
                        )).scalar_one_or_none()
                        if existing_notif:
                            continue

                        title = "家人漏打卡提醒"
                        content = (
                            f"您正在共同管理的 {owner_nickname} 今日 {t} 的 "
                            f"{plan.drug_name} 已超过 {GRACE_MINUTES} 分钟未打卡，请联系提醒"
                        )
                        db.add(NotificationLog(
                            user_id=mgr.manager_user_id,
                            source_type=SOURCE_TYPE,
                            source_id=unique_int_id,
                            title=title,
                            content=content,
                            status="pending",
                            scheduled_time=now,
                        ))

            await db.commit()
            logger.info("[PRD-468] miss_check_medication_reminders completed at %s", now.isoformat())
        except Exception:
            await db.rollback()
            logger.exception("[PRD-468] miss_check_medication_reminders error")
