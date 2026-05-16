"""[PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药计划状态自动流转服务。

设计要点：
- 不新增任何数据表，仅基于 MedicationReminder 现有字段（status / start_date /
  end_date / long_term / reminder_enabled）。
- 函数 ``auto_flow_medication_status`` 设计为幂等：每次调用都会全量扫描受影响
  用户的全部用药计划，并按以下规则转换 status：

  规则：
    1. status 当前在 (active, archived) 之间流转。status 为 deleted 不动。
    2. 未开始 (today < start_date)：
        - 若 status=='active' → 不强制转换，但 reminder_enabled 保持原值；
          (列表 Tab 通过 start/end_date 判定为「未开始」，不依赖 status 字段)
    3. 进行中 (start_date <= today <= end_date 或 long_term=True)：
        - 若 status=='archived' → 转 active，同时把 reminder_enabled 设为 True
          （避免已归档复活后用户依然收不到提醒）。
    4. 已结束 (end_date < today，且非 long_term)：
        - 若 status=='active' → 转 archived。

可在 /api/medication-plans/hero-count 与 /api/medication-reminder/today 接口
内懒触发一次（避免完全依赖外部定时任务）。也可由 APScheduler / cron 每日
00:01 调用 ``auto_flow_medication_status(db, user_id=None)`` 做全量扫描。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MedicationReminder


async def auto_flow_medication_status(
    db: AsyncSession,
    user_id: Optional[int] = None,
) -> dict:
    """按规则同步 MedicationReminder 的 status / reminder_enabled。

    Args:
        db: 异步 SQLAlchemy 会话
        user_id: 仅处理某个用户；None 表示全表扫描（适合定时任务）
    Returns:
        统计 dict：{"activated": int, "archived": int, "scanned": int}
    """
    today = date.today()
    stmt = select(MedicationReminder).where(
        MedicationReminder.status.in_(["active", "archived"]),
    )
    if user_id is not None:
        stmt = stmt.where(MedicationReminder.user_id == user_id)
    reminders = (await db.execute(stmt)).scalars().all()

    activated = 0
    archived = 0
    for r in reminders:
        long_term = bool(r.long_term)
        start_d = r.start_date
        end_d = r.end_date

        if long_term or (start_d and end_d and start_d <= today <= end_d) or (
            start_d and start_d <= today and end_d is None
        ):
            # 仅在「显式禁用提醒」时自动 resurrect：避免把用户手动归档的计划复活。
            # 典型场景：定时任务在某条计划到达 start_date 当天自动启用（前置创建时
            # 业务可把 reminder_enabled 置 False 作为「待启用」标记）。
            if r.status == "archived" and r.reminder_enabled is False:
                r.status = "active"
                r.reminder_enabled = True
                activated += 1
            continue

        if end_d and end_d < today and not long_term:
            if r.status == "active":
                r.status = "archived"
                archived += 1
            continue

    if activated or archived:
        await db.flush()

    return {"activated": activated, "archived": archived, "scanned": len(reminders)}
