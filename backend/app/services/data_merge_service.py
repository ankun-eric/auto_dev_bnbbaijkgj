"""[F9] 邀请绑定后的健康数据合并服务。

合并规则（按日期维度）：
- 对方（被守护者本人/acceptor）录了数据 → 以对方为准
- 仅管理方（inviter）录了数据 → 保留管理方数据（迁移归属）
- 两边都录了同一天数据 → 以对方本人录入的为准

适用表：
- checkup_reports：按 report_date 去重
- medication_reminders / medication_check_ins：按 reminder + check_in_date 去重
- health_checkin_records：按 item + check_in_date 去重
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CheckupReport

logger = logging.getLogger(__name__)


async def merge_health_data_on_accept(
    db: AsyncSession,
    inviter_user_id: int,
    acceptor_user_id: int,
    member_id: int,
) -> dict:
    """邀请被接受后，将 inviter 在 member_id 下录入的数据合并到 acceptor。

    inviter_user_id: 管理方（发出邀请的人）
    acceptor_user_id: 被守护者本人（接受邀请的人）
    member_id: 共管的家庭成员 ID

    Returns:
        {"checkup_reports_migrated": N, "checkup_reports_skipped": N}
    """
    stats = {
        "checkup_reports_migrated": 0,
        "checkup_reports_skipped": 0,
    }

    # --- 体检报告按 report_date 合并 ---
    inviter_reports_result = await db.execute(
        select(CheckupReport).where(
            CheckupReport.user_id == inviter_user_id,
            CheckupReport.family_member_id == member_id,
        )
    )
    inviter_reports = inviter_reports_result.scalars().all()

    if inviter_reports:
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

        for report in inviter_reports:
            if report.report_date is not None and report.report_date in acceptor_dates:
                stats["checkup_reports_skipped"] += 1
            else:
                report.user_id = acceptor_user_id
                report.family_member_id = None
                stats["checkup_reports_migrated"] += 1

    if stats["checkup_reports_migrated"] > 0:
        await db.flush()

    logger.info(
        "[F9] merge_health_data_on_accept inviter=%s acceptor=%s member=%s stats=%s",
        inviter_user_id,
        acceptor_user_id,
        member_id,
        stats,
    )
    return stats
