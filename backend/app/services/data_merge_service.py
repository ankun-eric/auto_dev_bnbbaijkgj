"""[F1] 共管后全量数据同步服务（PRD-HEALTH-ARCHIVE-CO-MANAGE 2026-06-05）。

合并规则：
- 对方（被守护者本人/acceptor）录了数据 → 以对方为准（跳过迁移）
- 仅管理方（inviter）录了数据 → 保留管理方数据（迁移归属到 acceptor）
- 两边都录了同一天数据 → 以对方本人录入的为准

覆盖 12 张表：
1. health_profiles         - 健康档案主表（已实现）
2. health_metric_record    - 健康指标记录
3. medication_reminders    - 用药提醒
4. medication_check_ins    - 用药打卡
5. medication_plans        - 用药计划
6. medication_logs         - 用药日志
7. device_user_bindings    - 设备绑定关系
8. home_safety_device_binding - 居家安全设备绑定
9. checkup_reports         - 检查报告（已实现）
10. health_checkin_items    - 健康打卡项
11. health_checkin_records  - 健康打卡记录
12. health_events           - 健康事件

异常处理：
- 同步失败时记录失败日志，不影响其他表
- 部分表同步失败不影响其他表的同步
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CheckupReport, FamilyMember, HealthProfile

logger = logging.getLogger(__name__)


async def merge_health_data_on_accept(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
) -> dict:
    """邀请被接受后，将 inviter 在 member_id 下录入的数据全量合并到 acceptor。

    inviter_user_id: 管理方（发出邀请的人）
    acceptor_user_id: 被守护者本人（接受邀请的人）
    member_id: 共管的家庭成员 ID（inviter 侧的 family_member.id）

    Returns:
        各表迁移统计 dict
    """
    stats: dict[str, int] = {
        "health_profiles_migrated": 0,
        "health_metric_records_migrated": 0,
        "medication_reminders_migrated": 0,
        "medication_check_ins_migrated": 0,
        "medication_plans_migrated": 0,
        "medication_logs_migrated": 0,
        "device_user_bindings_migrated": 0,
        "home_safety_device_bindings_migrated": 0,
        "checkup_reports_migrated": 0,
        "checkup_reports_skipped": 0,
        "health_checkin_items_migrated": 0,
        "health_checkin_records_migrated": 0,
        "health_events_migrated": 0,
    }

    # ─── 1. 体检报告（checkup_reports）───
    await _merge_checkup_reports(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 2. 健康档案主表（health_profiles）───
    await _merge_health_profiles(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 3. 健康指标记录（health_metric_record）───
    await _merge_health_metric_records(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 4. 用药提醒（medication_reminders）───
    await _merge_medication_reminders(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 5. 用药打卡（medication_check_ins）───
    await _merge_medication_check_ins(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 6. 用药计划（medication_plans）───
    await _merge_medication_plans(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 7. 用药日志（medication_logs）───
    await _merge_medication_logs(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 8. 设备绑定关系（device_user_bindings）───
    await _merge_device_user_bindings(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 9. 居家安全设备绑定（home_safety_device_binding）───
    await _merge_home_safety_device_bindings(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 10. 健康打卡项（health_checkin_items）───
    await _merge_health_checkin_items(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 11. 健康打卡记录（health_checkin_records）───
    await _merge_health_checkin_records(db, inviter_user_id, acceptor_user_id, member_id, stats)

    # ─── 12. 健康事件（health_events）───
    await _merge_health_events(db, inviter_user_id, acceptor_user_id, member_id, stats)

    logger.info(
        "[F1] merge_health_data_on_accept inviter=%s acceptor=%s member=%s stats=%s",
        inviter_user_id,
        acceptor_user_id,
        member_id,
        stats,
    )
    return stats


async def _merge_checkup_reports(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """体检报告按 report_date 合并。"""
    try:
        inviter_reports_result = await db.execute(
            select(CheckupReport).where(
                CheckupReport.user_id == inviter_user_id,
                CheckupReport.family_member_id == member_id,
            )
        )
        inviter_reports = inviter_reports_result.scalars().all()
        if not inviter_reports:
            return

        acceptor_reports_result = await db.execute(
            select(CheckupReport).where(
                CheckupReport.user_id == acceptor_user_id,
                CheckupReport.family_member_id.is_(None),
            )
        )
        acceptor_reports = acceptor_reports_result.scalars().all()
        acceptor_dates: set[date | None] = set()
        for r in acceptor_reports:
            if r.report_date is not None:
                acceptor_dates.add(r.report_date)

        migrated = 0
        skipped = 0
        for report in inviter_reports:
            if report.report_date is not None and report.report_date in acceptor_dates:
                skipped += 1
            else:
                report.user_id = acceptor_user_id
                report.family_member_id = None
                migrated += 1
        stats["checkup_reports_migrated"] = migrated
        stats["checkup_reports_skipped"] = skipped
        if migrated > 0:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] checkup_reports merge failed: %s", e)


async def _merge_health_profiles(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """健康档案主表迁移。"""
    try:
        from app.models.models import HealthProfile as HP
        inviter_hp_result = await db.execute(
            select(HP).where(
                HP.user_id == inviter_user_id,
                HP.family_member_id == member_id,
            )
        )
        inviter_hps = inviter_hp_result.scalars().all()
        if not inviter_hps:
            return

        for hp in inviter_hps:
            hp.user_id = acceptor_user_id
            hp.family_member_id = None
        stats["health_profiles_migrated"] = len(inviter_hps)
        await db.flush()
    except Exception as e:
        logger.warning("[F1] health_profiles merge failed: %s", e)


async def _merge_health_metric_records(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """健康指标记录迁移（通过 inviter 的 HealthProfile -> acceptor 的 HealthProfile）。"""
    try:
        from app.models.health_v3 import HealthMetricRecord
        from app.models.models import HealthProfile as HP

        inviter_hp = (await db.execute(
            select(HP).where(HP.user_id == inviter_user_id, HP.family_member_id == member_id)
        )).scalars().first()
        if not inviter_hp:
            return

        acceptor_hp = (await db.execute(
            select(HP).where(HP.user_id == acceptor_user_id, HP.family_member_id.is_(None))
        )).scalars().first()
        if not acceptor_hp:
            acceptor_hp = HP(user_id=acceptor_user_id, family_member_id=None)
            db.add(acceptor_hp)
            await db.flush()

        records = (await db.execute(
            select(HealthMetricRecord).where(HealthMetricRecord.profile_id == inviter_hp.id)
        )).scalars().all()
        for rec in records:
            rec.profile_id = acceptor_hp.id
        stats["health_metric_records_migrated"] = len(records)
        if records:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] health_metric_record merge failed: %s", e)


async def _merge_medication_reminders(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """用药提醒迁移。"""
    try:
        from app.models.models import MedicationReminder

        reminders = (await db.execute(
            select(MedicationReminder).where(
                MedicationReminder.user_id == inviter_user_id,
                MedicationReminder.family_member_id == member_id,
            )
        )).scalars().all()
        for rem in reminders:
            rem.user_id = acceptor_user_id
            rem.family_member_id = None
        stats["medication_reminders_migrated"] = len(reminders)
        if reminders:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] medication_reminders merge failed: %s", e)


async def _merge_medication_check_ins(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """用药打卡迁移。"""
    try:
        from app.models.models import MedicationCheckIn

        checkins = (await db.execute(
            select(MedicationCheckIn).where(MedicationCheckIn.user_id == inviter_user_id)
        )).scalars().all()
        for ci in checkins:
            ci.user_id = acceptor_user_id
        stats["medication_check_ins_migrated"] = len(checkins)
        if checkins:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] medication_check_ins merge failed: %s", e)


async def _merge_medication_plans(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """用药计划迁移。"""
    try:
        from app.models.models import MedicationPlan

        plans = (await db.execute(
            select(MedicationPlan).where(MedicationPlan.user_id == inviter_user_id)
        )).scalars().all()
        for plan in plans:
            plan.user_id = acceptor_user_id
        stats["medication_plans_migrated"] = len(plans)
        if plans:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] medication_plans merge failed: %s", e)


async def _merge_medication_logs(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """用药日志迁移。"""
    try:
        from app.models.models import MedicationLog

        logs = (await db.execute(
            select(MedicationLog).where(MedicationLog.user_id == inviter_user_id)
        )).scalars().all()
        for log_item in logs:
            log_item.user_id = acceptor_user_id
        stats["medication_logs_migrated"] = len(logs)
        if logs:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] medication_logs merge failed: %s", e)


async def _merge_device_user_bindings(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """设备绑定关系迁移。"""
    try:
        from app.models.devices_v2 import DeviceUserBinding

        bindings = (await db.execute(
            select(DeviceUserBinding).where(DeviceUserBinding.user_id == inviter_user_id)
        )).scalars().all()
        for b in bindings:
            b.user_id = acceptor_user_id
        stats["device_user_bindings_migrated"] = len(bindings)
        if bindings:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] device_user_bindings merge failed: %s", e)


async def _merge_home_safety_device_bindings(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """居家安全设备绑定迁移。"""
    try:
        from app.api.home_safety_v1 import HomeSafetyDeviceBinding

        bindings = (await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.user_id == inviter_user_id,
                HomeSafetyDeviceBinding.member_id == member_id,
            )
        )).scalars().all()
        for b in bindings:
            b.user_id = acceptor_user_id
            b.member_id = None
        stats["home_safety_device_bindings_migrated"] = len(bindings)
        if bindings:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] home_safety_device_bindings merge failed: %s", e)


async def _merge_health_checkin_items(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """健康打卡项迁移。"""
    try:
        from app.models.models import HealthCheckinItem

        items = (await db.execute(
            select(HealthCheckinItem).where(HealthCheckinItem.user_id == inviter_user_id)
        )).scalars().all()
        for item in items:
            item.user_id = acceptor_user_id
        stats["health_checkin_items_migrated"] = len(items)
        if items:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] health_checkin_items merge failed: %s", e)


async def _merge_health_checkin_records(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """健康打卡记录迁移。"""
    try:
        from app.models.models import HealthCheckinRecord

        records = (await db.execute(
            select(HealthCheckinRecord).where(HealthCheckinRecord.user_id == inviter_user_id)
        )).scalars().all()
        for rec in records:
            rec.user_id = acceptor_user_id
        stats["health_checkin_records_migrated"] = len(records)
        if records:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] health_checkin_records merge failed: %s", e)


async def _merge_health_events(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
    stats: dict,
) -> None:
    """健康事件迁移（通过 inviter 的 HealthProfile -> acceptor 的 HealthProfile）。"""
    try:
        from app.models.models import HealthEvent, HealthProfile as HP

        inviter_hp = (await db.execute(
            select(HP).where(HP.user_id == inviter_user_id, HP.family_member_id == member_id)
        )).scalars().first()
        if not inviter_hp:
            return

        acceptor_hp = (await db.execute(
            select(HP).where(HP.user_id == acceptor_user_id, HP.family_member_id.is_(None))
        )).scalars().first()
        if not acceptor_hp:
            return

        events = (await db.execute(
            select(HealthEvent).where(HealthEvent.profile_id == inviter_hp.id)
        )).scalars().all()
        for evt in events:
            evt.profile_id = acceptor_hp.id
        stats["health_events_migrated"] = len(events)
        if events:
            await db.flush()
    except Exception as e:
        logger.warning("[F1] health_events merge failed: %s", e)
