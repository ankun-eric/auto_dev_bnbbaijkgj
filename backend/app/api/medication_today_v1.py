"""[PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] ai-home 首页优化 - 同源接口

按 PRD §5 「接口契约」实现以下两个端点：

1. GET /api/medication/today
   - 同时供：
     · ai-home「今日用药」按钮红点
     · 健康档案 Hero「今日用药」徽标
     · 「今日用药」抽屉内容渲染
   - 返回结构：
     {
       "code": 0,
       "data": {
         "hasTodayMedication": bool,
         "items": [ { planId, medName, time, dose, status } ],
         "summary": { "total": int, "done": int, "remaining": int }
       }
     }
   - 入参：consultant_id (Optional) —— 按咨询人维度筛选；同时兼容 patient_id

2. GET /api/medication/plans/exists?medName=xxx
   - 查询某药品（按药品名）是否已加入用药计划
   - 入参：medName (必填), consultant_id (Optional)
   - 返回：{ "code": 0, "data": { "exists": bool, "planId": int|null } }

注：实际数据复用 medication_reminder 已有的 MedicationPlan / MedicationLog 数据模型，
本模块只是按 PRD 规范包装一层 API，不重复实现 CRUD。
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import MedicationLog, MedicationPlan, User

router = APIRouter(
    prefix="/api/medication",
    tags=["PRD-AI-HOME-OPTIM-FINAL-V1 同源今日用药"],
)
logger = logging.getLogger(__name__)


@router.get("/today")
async def get_today_medication(
    consultant_id: Optional[int] = Query(None, description="咨询人 family_member.id；本人传 0 或 None"),
    patient_id: Optional[int] = Query(None, description="向后兼容字段，与 consultant_id 等价"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-AI-HOME-OPTIM-FINAL-V1 §5.1] 同源「今日用药」接口。

    返回当前用户（或指定咨询人）今天的全部用药计划条目列表，
    以及汇总统计 `hasTodayMedication` / `summary`。

    红点判定规则（来自 PRD §1.4）：
      - hasTodayMedication=True 即「今天有用药计划」
      - 不区分是否已打卡 —— 严格按"有计划就亮"
    """
    today = date.today()
    effective_pid = consultant_id if consultant_id is not None else patient_id

    plan_stmt = (
        select(MedicationPlan)
        .where(MedicationPlan.user_id == current_user.id)
        .where(MedicationPlan.enabled == True)  # noqa: E712
    )
    # consultant_id 为 0 或负数视为本人（patient_id IS NULL）
    if effective_pid is not None and effective_pid > 0:
        plan_stmt = plan_stmt.where(MedicationPlan.patient_id == effective_pid)
    plans = (await db.execute(plan_stmt)).scalars().all()

    plan_ids = [p.id for p in plans]
    logs_map: dict[tuple[int, str], MedicationLog] = {}
    if plan_ids:
        log_stmt = select(MedicationLog).where(
            MedicationLog.plan_id.in_(plan_ids),
            MedicationLog.log_date == today,
            MedicationLog.user_id == current_user.id,
            MedicationLog.revoked == False,  # noqa: E712
        )
        for log in (await db.execute(log_stmt)).scalars().all():
            logs_map[(log.plan_id, log.scheduled_time)] = log

    items = []
    total = 0
    done = 0
    for p in plans:
        sched = list(p.schedule or [])
        for t in sched:
            total += 1
            checked = (p.id, t) in logs_map
            if checked:
                done += 1
            items.append(
                {
                    "planId": p.id,
                    "medName": p.drug_name,
                    "time": t,
                    "dose": p.dosage,
                    "status": "done" if checked else "pending",
                }
            )

    items.sort(key=lambda x: (x["time"], x["planId"]))
    has_today = len(items) > 0
    return {
        "code": 0,
        "data": {
            "hasTodayMedication": has_today,
            "items": items,
            "summary": {
                "total": total,
                "done": done,
                "remaining": max(0, total - done),
            },
        },
    }


@router.get("/plans/exists")
async def medication_plan_exists(
    medName: str = Query(..., description="药品名称（按精确匹配查询）"),
    consultant_id: Optional[int] = Query(None, description="按咨询人维度判定"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-AI-HOME-OPTIM-FINAL-V1 §5.2] 查询某药品是否已加入用药计划。

    给「加入用药计划」按钮判定「✓ 已加入」灰态使用。
    """
    stmt = (
        select(MedicationPlan)
        .where(MedicationPlan.user_id == current_user.id)
        .where(MedicationPlan.drug_name == medName)
        .where(MedicationPlan.enabled == True)  # noqa: E712
    )
    if consultant_id is not None and consultant_id > 0:
        stmt = stmt.where(MedicationPlan.patient_id == consultant_id)
    plan = (await db.execute(stmt)).scalars().first()
    return {
        "code": 0,
        "data": {
            "exists": plan is not None,
            "planId": plan.id if plan else None,
        },
    }
