"""[PRD-439] 用药提醒 API。

9 个端点：
- GET    /api/medication-reminder/plans
- POST   /api/medication-reminder/plans
- PUT    /api/medication-reminder/plans/{plan_id}
- DELETE /api/medication-reminder/plans/{plan_id}
- GET    /api/medication-reminder/today
- POST   /api/medication-reminder/check
- POST   /api/medication-reminder/uncheck
- GET    /api/medication-reminder/badge
- GET    /api/medication-reminder/appointments
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    MedicationLog,
    MedicationPlan,
    MerchantStore,
    OrderItem,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from app.schemas.medication_reminder import (
    AppointmentItem,
    BadgeMedicationDetail,
    BadgeOrderBreakdown,
    BadgeOrderDetail,
    BadgeResponse,
    CheckRequest,
    CheckResponse,
    MedicationPlanCreate,
    MedicationPlanOut,
    MedicationPlanUpdate,
    TodayMedicationItem,
    UncheckRequest,
)


# [PRD-BELL-UNIFIED-V1 2026-05-19] 铃铛红点合并计数 / 待办订单口径
# 6 种"球在用户脚下"的订单状态。pending_shipment（待发货）、refunding（退款中）、
# completed / cancelled / expired / refunded 等终态不进入红点。
BELL_PENDING_ORDER_STATUSES = [
    UnifiedOrderStatus.pending_payment,
    UnifiedOrderStatus.pending_appointment,
    UnifiedOrderStatus.appointed,
    UnifiedOrderStatus.pending_use,
    UnifiedOrderStatus.partial_used,
    UnifiedOrderStatus.pending_receipt,
]

BELL_PENDING_ORDER_STATUS_VALUES = {s.value for s in BELL_PENDING_ORDER_STATUSES}


def _order_status_text(status: UnifiedOrderStatus) -> str:
    return {
        UnifiedOrderStatus.pending_payment: "待支付",
        UnifiedOrderStatus.pending_appointment: "待预约",
        UnifiedOrderStatus.appointed: "已预约",
        UnifiedOrderStatus.pending_use: "待核销",
        UnifiedOrderStatus.partial_used: "部分核销",
        UnifiedOrderStatus.pending_receipt: "待收货",
    }.get(status, getattr(status, "value", str(status)))

router = APIRouter(prefix="/api/medication-reminder", tags=["PRD-439 用药提醒"])
logger = logging.getLogger(__name__)


def _validate_schedule(schedule: List[str]) -> List[str]:
    """显式校验 ["HH:MM", ...]，违规直接抛 400（友好 detail）。"""
    if not schedule:
        raise HTTPException(status_code=400, detail="schedule 至少 1 项")
    out: List[str] = []
    for v in schedule:
        if not isinstance(v, str) or len(v) != 5 or v[2] != ":":
            raise HTTPException(status_code=400, detail=f"时间格式应为 HH:MM：{v}")
        try:
            h, m = int(v[:2]), int(v[3:])
        except Exception:
            raise HTTPException(status_code=400, detail=f"时间格式错：{v}")
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise HTTPException(status_code=400, detail=f"时间超出范围：{v}")
        out.append(v)
    return out


# ─────────────────── 用药计划 CRUD ───────────────────


@router.get("/plans", response_model=List[MedicationPlanOut])
async def list_plans(
    patient_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MedicationPlan).where(MedicationPlan.user_id == current_user.id)
    if patient_id is not None:
        stmt = stmt.where(MedicationPlan.patient_id == patient_id)
    stmt = stmt.order_by(MedicationPlan.created_at.desc())
    res = await db.execute(stmt)
    plans = res.scalars().all()
    return [_plan_to_out(p) for p in plans]


@router.post("/plans", response_model=MedicationPlanOut)
async def create_plan(
    body: MedicationPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = _validate_schedule(list(body.schedule))
    plan = MedicationPlan(
        user_id=current_user.id,
        patient_id=body.patient_id,
        drug_name=body.drug_name,
        dosage=body.dosage,
        schedule=schedule,
        note=body.note,
        enabled=body.enabled,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return _plan_to_out(plan)


@router.put("/plans/{plan_id}", response_model=MedicationPlanOut)
async def update_plan(
    plan_id: int,
    body: MedicationPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_user_plan_or_404(db, current_user.id, plan_id)
    if body.drug_name is not None:
        plan.drug_name = body.drug_name
    if body.dosage is not None:
        plan.dosage = body.dosage
    if body.schedule is not None:
        plan.schedule = _validate_schedule(list(body.schedule))
    if body.note is not None:
        plan.note = body.note
    if body.enabled is not None:
        plan.enabled = body.enabled
    if body.patient_id is not None:
        plan.patient_id = body.patient_id
    await db.commit()
    await db.refresh(plan)
    return _plan_to_out(plan)


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_user_plan_or_404(db, current_user.id, plan_id)
    # 物理删 + 联带打卡日志
    await db.execute(
        MedicationLog.__table__.delete().where(MedicationLog.plan_id == plan_id)
    )
    await db.delete(plan)
    await db.commit()
    return {"ok": True}


# ─────────────────── 今日用药 / 打卡 ───────────────────


@router.get("/today", response_model=List[TodayMedicationItem])
async def today_medications(
    patient_id: Optional[int] = Query(None),
    # [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F10/F11 2026-05-18]
    # 增加 consultant_id 入参：与 patient_id 等价，按"咨询人 ID"维度筛选今日用药提醒。
    # 同时传入时以 consultant_id 优先，兼容前端两种调用方式（识药卡片用 consultant_id，
    # 历史调用方继续用 patient_id）。
    consultant_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    plan_stmt = (
        select(MedicationPlan)
        .where(MedicationPlan.user_id == current_user.id)
        .where(MedicationPlan.enabled == True)  # noqa: E712
    )
    effective_pid = consultant_id if consultant_id is not None else patient_id
    if effective_pid is not None:
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

    items: List[TodayMedicationItem] = []
    for p in plans:
        sched = list(p.schedule or [])
        for t in sched:
            log = logs_map.get((p.id, t))
            items.append(
                TodayMedicationItem(
                    plan_id=p.id,
                    drug_name=p.drug_name,
                    dosage=p.dosage,
                    scheduled_time=t,
                    note=p.note,
                    checked=bool(log),
                    checked_at=log.checked_at.strftime("%H:%M") if log else None,
                    log_id=log.id if log else None,
                )
            )
    items.sort(key=lambda x: (x.scheduled_time, x.plan_id))
    return items


@router.post("/check", response_model=CheckResponse)
async def check_in(
    body: CheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_user_plan_or_404(db, current_user.id, body.plan_id)
    log_date = body.log_date or date.today()
    # 校验时间槽存在
    sched = list(plan.schedule or [])
    if body.scheduled_time not in sched:
        raise HTTPException(status_code=400, detail="scheduled_time 不在该用药计划内")

    # 复用已存在的有效 log（同 plan_id + log_date + scheduled_time + 未撤销）
    existing = (await db.execute(
        select(MedicationLog).where(
            MedicationLog.plan_id == plan.id,
            MedicationLog.log_date == log_date,
            MedicationLog.scheduled_time == body.scheduled_time,
            MedicationLog.revoked == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if existing:
        return CheckResponse(
            log_id=existing.id, checked_at=existing.checked_at.strftime("%H:%M")
        )

    log = MedicationLog(
        plan_id=plan.id,
        user_id=current_user.id,
        log_date=log_date,
        scheduled_time=body.scheduled_time,
        checked_at=datetime.utcnow(),
        revoked=False,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return CheckResponse(log_id=log.id, checked_at=log.checked_at.strftime("%H:%M"))


@router.post("/uncheck")
async def uncheck(
    body: UncheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    log = (await db.execute(
        select(MedicationLog).where(MedicationLog.id == body.log_id)
    )).scalar_one_or_none()
    if not log or log.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="打卡记录不存在")
    log.revoked = True
    await db.commit()
    return {"ok": True}


# ─────────────────── 徽标 / 待核销预约 ───────────────────


@router.get("/badge", response_model=BadgeResponse)
async def badge(
    patient_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-BELL-UNIFIED-V1 2026-05-19] 铃铛红点合并计数

    红点数字 = 用药待服条数 + 待处理订单条数（6 个"球在用户脚下"状态合并）。
    - 用药待服：今天计划要吃但未点"已服用"的，按"次"计数（08:00/14:00/20:00 算 3 条）
    - 订单状态计入红点的有 6 个：
        pending_payment / pending_appointment / appointed / pending_use / partial_used / pending_receipt
    - 紧急标记 has_urgent：
        medication.has_urgent → 存在已过点（scheduled_time < 当前时间）但未打卡的条目
        order.has_urgent → 存在 pending_payment 订单（口径：30 分钟内即将超时也算紧急；这里简化为有任意待支付即视为紧急，前端可再细化）
    旧字段 medication_unchecked / appointment_pending / total 保留，保障旧客户端向后兼容。
    """
    today = date.today()
    now_dt = datetime.now()
    now_hhmm = now_dt.strftime("%H:%M")
    plan_stmt = (
        select(MedicationPlan)
        .where(MedicationPlan.user_id == current_user.id)
        .where(MedicationPlan.enabled == True)  # noqa: E712
    )
    if patient_id is not None:
        plan_stmt = plan_stmt.where(MedicationPlan.patient_id == patient_id)
    plans = (await db.execute(plan_stmt)).scalars().all()

    plan_ids = [p.id for p in plans]
    checked_keys: set[tuple[int, str]] = set()
    if plan_ids:
        log_stmt = select(MedicationLog.plan_id, MedicationLog.scheduled_time).where(
            MedicationLog.plan_id.in_(plan_ids),
            MedicationLog.log_date == today,
            MedicationLog.user_id == current_user.id,
            MedicationLog.revoked == False,  # noqa: E712
        )
        for plan_id, st in (await db.execute(log_stmt)).all():
            checked_keys.add((plan_id, st))

    medication_unchecked = 0
    medication_has_urgent = False
    for p in plans:
        for t in (p.schedule or []):
            if (p.id, t) not in checked_keys:
                medication_unchecked += 1
                if t < now_hhmm:
                    medication_has_urgent = True

    # 订单：6 状态合并计数 + 状态细分 + 紧急标记
    order_stmt = select(UnifiedOrder).where(
        UnifiedOrder.user_id == current_user.id,
        UnifiedOrder.status.in_(BELL_PENDING_ORDER_STATUSES),
    )
    orders = (await db.execute(order_stmt)).scalars().all()
    breakdown = BadgeOrderBreakdown()
    order_has_urgent = False
    for o in orders:
        sv = getattr(o.status, "value", str(o.status))
        if sv == "pending_payment":
            breakdown.pending_payment += 1
            order_has_urgent = True  # 待支付天然紧急（用户随时可能丢单）
        elif sv == "pending_appointment":
            breakdown.pending_appointment += 1
        elif sv == "appointed":
            breakdown.appointed += 1
        elif sv == "pending_use":
            breakdown.pending_use += 1
        elif sv == "partial_used":
            breakdown.partial_used += 1
        elif sv == "pending_receipt":
            breakdown.pending_receipt += 1

    order_count = (
        breakdown.pending_payment + breakdown.pending_appointment + breakdown.appointed
        + breakdown.pending_use + breakdown.partial_used + breakdown.pending_receipt
    )
    total = medication_unchecked + order_count
    return BadgeResponse(
        medication_unchecked=medication_unchecked,
        appointment_pending=order_count,
        total=total,
        medication=BadgeMedicationDetail(
            count=medication_unchecked,
            has_urgent=medication_has_urgent,
        ),
        order=BadgeOrderDetail(
            count=order_count,
            has_urgent=order_has_urgent,
            breakdown=breakdown,
        ),
    )


@router.get("/appointments", response_model=List[AppointmentItem])
async def appointments(
    patient_id: Optional[int] = Query(None),
    status_in: Optional[str] = Query(
        None,
        description=(
            "逗号分隔的 UnifiedOrderStatus 集合。"
            "默认（不传时）使用 PRD-BELL-UNIFIED-V1 的 6 状态合并："
            "pending_payment,pending_appointment,appointed,pending_use,partial_used,pending_receipt。"
            "传入未知值会被忽略。"
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-BELL-UNIFIED-V1 2026-05-19] 铃铛抽屉订单列表（6 状态合并）

    与 /badge 的口径完全一致：
      pending_payment（待支付）/ pending_appointment（待预约）/ appointed（已预约）
      pending_use（待核销）/ partial_used（部分核销）/ pending_receipt（待收货）
    """
    # 解析 status_in；未传或解析后为空，使用 6 状态合并默认值
    if status_in:
        raw = [s.strip() for s in status_in.split(",") if s.strip()]
        statuses = []
        for s in raw:
            if s in BELL_PENDING_ORDER_STATUS_VALUES:
                statuses.append(UnifiedOrderStatus(s))
        if not statuses:
            statuses = list(BELL_PENDING_ORDER_STATUSES)
    else:
        statuses = list(BELL_PENDING_ORDER_STATUSES)

    stmt = (
        select(UnifiedOrder)
        .where(UnifiedOrder.user_id == current_user.id)
        .where(UnifiedOrder.status.in_(statuses))
        .options(selectinload(UnifiedOrder.items), selectinload(UnifiedOrder.store))
        .order_by(UnifiedOrder.created_at.desc())
    )
    orders = (await db.execute(stmt)).scalars().all()

    items: List[AppointmentItem] = []
    for o in orders:
        first_item = o.items[0] if o.items else None
        appt_dt = None
        if first_item and getattr(first_item, "appointment_time", None):
            appt_dt = first_item.appointment_time
        location = None
        store = getattr(o, "store", None)
        if store is not None:
            store_name = getattr(store, "store_name", None)
            store_addr = getattr(store, "address", None)
            location = ("｜".join([s for s in [store_name, store_addr] if s])
                        ) or store_name or store_addr
        # 部分核销剩余次数
        total_redeem = getattr(first_item, "total_redeem_count", None) if first_item else None
        used_redeem = getattr(first_item, "used_redeem_count", None) if first_item else None
        remaining_redeem = (
            (total_redeem - used_redeem)
            if (isinstance(total_redeem, int) and isinstance(used_redeem, int))
            else None
        )
        amount_val = None
        try:
            if getattr(o, "total_amount", None) is not None:
                amount_val = f"{float(o.total_amount):.2f}"
        except Exception:
            amount_val = None
        items.append(
            AppointmentItem(
                order_id=o.id,
                order_no=getattr(o, "order_no", None),
                service_name=(first_item.product_name if first_item else "—"),
                appointed_at=appt_dt.strftime("%Y-%m-%d %H:%M") if appt_dt else None,
                location=location,
                status_text=_order_status_text(o.status),
                qrcode_url=None,
                verification_code=getattr(first_item, "verification_code", None) if first_item else None,
                status=getattr(o.status, "value", str(o.status)),
                amount=amount_val,
                quantity=getattr(first_item, "quantity", None) if first_item else None,
                spec=getattr(first_item, "sku_name", None) if first_item else None,
                created_at=o.created_at.strftime("%Y-%m-%d %H:%M") if getattr(o, "created_at", None) else None,
                remaining_redeem_count=remaining_redeem,
                total_redeem_count=total_redeem,
                tracking_company=getattr(o, "tracking_company", None),
                tracking_number=getattr(o, "tracking_number", None),
            )
        )
    # 优先按 appointed_at 排序（无值放最后），再按订单 id desc
    items.sort(key=lambda x: (x.appointed_at or "9999", -x.order_id))
    return items


# ─────────────────── 内部辅助 ───────────────────


async def _get_user_plan_or_404(
    db: AsyncSession, user_id: int, plan_id: int
) -> MedicationPlan:
    plan = (await db.execute(
        select(MedicationPlan).where(MedicationPlan.id == plan_id)
    )).scalar_one_or_none()
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="用药计划不存在")
    return plan


def _plan_to_out(p: MedicationPlan) -> MedicationPlanOut:
    return MedicationPlanOut(
        id=p.id,
        user_id=p.user_id,
        patient_id=p.patient_id,
        drug_name=p.drug_name,
        dosage=p.dosage,
        schedule=list(p.schedule or []),
        note=p.note,
        enabled=bool(p.enabled),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )
