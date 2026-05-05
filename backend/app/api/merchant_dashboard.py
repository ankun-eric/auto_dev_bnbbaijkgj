"""
[门店预约看板与改期能力升级 v1.0] 门店端预约看板聚合接口

提供日/周/月三视图所需的预约数据聚合，全平台采用固定 9 段时段切片：
段号 1-9 对应 06:00-08:00 / 08:00-10:00 / 10:00-12:00 / 12:00-14:00 /
14:00-16:00 / 16:00-18:00 / 18:00-20:00 / 20:00-22:00 / 22:00-24:00。
凌晨段 00:00-06:00 不开放。

接口清单：
- GET  /api/merchant/dashboard/day                日视图（9 宫格）
- GET  /api/merchant/dashboard/week               周视图（7 列）
- GET  /api/merchant/dashboard/month              月视图（月历日聚合）
- GET  /api/merchant/dashboard/slot/{date}/{slot} 时段抽屉订单列表
- GET  /api/merchant/dashboard/time-slots         固定 9 段时段配置（公开）
- GET  /api/merchant/dashboard/month-day          月视图某天订单列表（左右两栏）
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    MerchantStore,
    MerchantStoreMembership,
    OrderItem,
    OrderRedemption,
    Product,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/merchant/dashboard", tags=["merchant-dashboard"])


# ─────────────── 固定 9 段时段配置 ───────────────

SLOT_HOURS: List[tuple[int, int]] = [
    (6, 8),   # slot 1
    (8, 10),  # slot 2
    (10, 12), # slot 3
    (12, 14), # slot 4
    (14, 16), # slot 5
    (16, 18), # slot 6
    (18, 20), # slot 7
    (20, 22), # slot 8
    (22, 24), # slot 9
]


def slot_label(slot_no: int) -> str:
    """slot 序号 1-9 → '06:00-08:00' 形式标签"""
    if not 1 <= slot_no <= 9:
        return ""
    h_start, h_end = SLOT_HOURS[slot_no - 1]
    end_str = "24:00" if h_end == 24 else f"{h_end:02d}:00"
    return f"{h_start:02d}:00-{end_str}"


def appointment_to_slot(dt: Optional[datetime]) -> Optional[int]:
    """订单 appointment_time → slot 序号 1-9（凌晨段返回 None）"""
    if not dt:
        return None
    h = dt.hour
    if h < 6:
        return None  # 凌晨段不归入 9 宫格
    for idx, (start, end) in enumerate(SLOT_HOURS, start=1):
        if start <= h < end:
            return idx
    return 9  # 22:00 后归入第 9 段


def slot_window(target_date: date, slot_no: int) -> tuple[datetime, datetime]:
    """slot 序号 → 该日的开始/结束 datetime"""
    h_start, h_end = SLOT_HOURS[slot_no - 1]
    start_dt = datetime.combine(target_date, time(h_start, 0))
    if h_end == 24:
        end_dt = datetime.combine(target_date + timedelta(days=1), time(0, 0))
    else:
        end_dt = datetime.combine(target_date, time(h_end, 0))
    return start_dt, end_dt


# ─────────────── 工具：解析 store_id + 鉴权 ───────────────

async def _resolve_store_ids_for_user(db: AsyncSession, user: User, store_id: Optional[int]) -> List[int]:
    """根据当前用户角色返回可见的 store_id 列表。

    - admin / super_admin：可指定任意 store_id；不指定则返回 [] 表示全部门店
    - merchant 角色：仅可访问其所属门店；指定 store_id 必须在权限范围内
    """
    role = getattr(user, "role", None)
    if hasattr(role, "value"):
        role = role.value
    role = str(role or "")

    # 管理员侧：可任意指定门店
    if role in ("admin", "super_admin"):
        if store_id is not None:
            return [int(store_id)]
        return []  # 空列表 = 不限制门店

    # 商家侧：从 MerchantStoreMembership 拿到关联门店
    member_rows = await db.execute(
        select(MerchantStoreMembership.store_id).where(
            MerchantStoreMembership.user_id == user.id,
        )
    )
    allowed = [int(r[0]) for r in member_rows.all()]
    if not allowed:
        # 兜底：通过 MerchantProfile.user_id 找门店
        from app.models.models import MerchantProfile
        prof_rows = await db.execute(
            select(MerchantStore.id).join(
                MerchantProfile, MerchantStore.merchant_id == MerchantProfile.id
            ).where(MerchantProfile.user_id == user.id)
        )
        allowed = [int(r[0]) for r in prof_rows.all()]

    if not allowed:
        raise HTTPException(status_code=403, detail="未关联任何门店")

    if store_id is None:
        # 商家未指定门店时取首个
        return [allowed[0]]
    if int(store_id) not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该门店")
    return [int(store_id)]


# ─────────────── 公共时段配置接口 ───────────────

@router.get("/time-slots")
async def get_time_slots() -> Dict[str, Any]:
    """返回固定 9 段时段配置，供客户端时段选择器使用"""
    return {
        "slots": [
            {"slot_no": idx, "label": slot_label(idx),
             "start_hour": SLOT_HOURS[idx - 1][0],
             "end_hour": SLOT_HOURS[idx - 1][1]}
            for idx in range(1, 10)
        ],
        "rule": "全平台固定 9 段时段（每段 2 小时，最早 06:00，最晚 24:00），凌晨 00:00-06:00 不开放",
    }


# ─────────────── 日视图（9 宫格） ───────────────

def _is_verified_status(status_val) -> bool:
    if hasattr(status_val, "value"):
        status_val = status_val.value
    return status_val in ("verified", "completed", "pending_receipt")


def _is_active_status(status_val) -> bool:
    """有效订单（含已核销）：用于"预约 N"统计"""
    if hasattr(status_val, "value"):
        status_val = status_val.value
    return status_val not in ("cancelled", "refund_success", "pending_payment")


@router.get("/day")
async def get_day_dashboard(
    target_date: date = Query(..., alias="date", description="目标日期 YYYY-MM-DD"),
    store_id: Optional[int] = Query(None, description="门店 ID，商家未指定时取首个"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """日视图（9 宫格）— 返回该日 9 个时段的统计数据。

    每格包含：slot_no / label / 预约总数 / 已核销数 / 已核销金额。
    """
    store_ids = await _resolve_store_ids_for_user(db, current_user, store_id)

    day_start = datetime.combine(target_date, time(0, 0))
    day_end = day_start + timedelta(days=1)

    # 查该日所有相关订单项（含订单状态、金额、时段）
    stmt = (
        select(OrderItem, UnifiedOrder)
        .join(UnifiedOrder, OrderItem.order_id == UnifiedOrder.id)
        .where(
            OrderItem.appointment_time.is_not(None),
            OrderItem.appointment_time >= day_start,
            OrderItem.appointment_time < day_end,
        )
    )
    if store_ids:
        stmt = stmt.where(UnifiedOrder.store_id.in_(store_ids))

    rows = (await db.execute(stmt)).all()

    # 初始化 9 格
    cells: Dict[int, Dict[str, Any]] = {
        i: {
            "slot_no": i,
            "label": slot_label(i),
            "appointment_count": 0,
            "verified_count": 0,
            "verified_amount": 0.0,
        }
        for i in range(1, 10)
    }

    total_appt = 0
    total_verified = 0
    total_verified_amount = 0.0
    overflow_count = 0  # 凌晨脏数据

    for item, order in rows:
        slot = appointment_to_slot(item.appointment_time)
        if slot is None:
            overflow_count += 1
            continue
        cell = cells[slot]
        if _is_active_status(order.status):
            cell["appointment_count"] += 1
            total_appt += 1
        if _is_verified_status(order.status):
            cell["verified_count"] += 1
            # 按订单金额平摊到每个 item（简化：使用 item.subtotal）
            amt = float(item.subtotal or 0)
            cell["verified_amount"] += amt
            total_verified += 1
            total_verified_amount += amt

    # 当前 slot 高亮（仅当 target_date == today）
    current_slot = None
    today = date.today()
    if target_date == today:
        current_slot = appointment_to_slot(datetime.now())

    return {
        "date": target_date.isoformat(),
        "store_ids": store_ids,
        "cells": [cells[i] for i in range(1, 10)],
        "summary": {
            "appointment_count": total_appt,
            "verified_count": total_verified,
            "verified_amount": round(total_verified_amount, 2),
            "overflow_count": overflow_count,
        },
        "current_slot": current_slot,
    }


# ─────────────── 周视图 ───────────────

@router.get("/week")
async def get_week_dashboard(
    target_date: date = Query(..., alias="date", description="周内任一日期 YYYY-MM-DD"),
    store_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """周视图 — 返回本周 7 天的聚合数据（预约 / 已核 / 收入）"""
    store_ids = await _resolve_store_ids_for_user(db, current_user, store_id)

    weekday = target_date.weekday()  # 周一 = 0
    week_start = target_date - timedelta(days=weekday)
    week_end_excl = week_start + timedelta(days=7)

    stmt = (
        select(OrderItem, UnifiedOrder)
        .join(UnifiedOrder, OrderItem.order_id == UnifiedOrder.id)
        .where(
            OrderItem.appointment_time.is_not(None),
            OrderItem.appointment_time >= datetime.combine(week_start, time(0, 0)),
            OrderItem.appointment_time < datetime.combine(week_end_excl, time(0, 0)),
        )
    )
    if store_ids:
        stmt = stmt.where(UnifiedOrder.store_id.in_(store_ids))

    rows = (await db.execute(stmt)).all()

    days: Dict[str, Dict[str, Any]] = {}
    for offset in range(7):
        d = (week_start + timedelta(days=offset)).isoformat()
        days[d] = {
            "date": d,
            "weekday": offset,  # 0 = 周一
            "appointment_count": 0,
            "verified_count": 0,
            "verified_amount": 0.0,
        }

    total_appt = total_verified = 0
    total_amount = 0.0

    for item, order in rows:
        d = item.appointment_time.date().isoformat()
        if d not in days:
            continue
        cell = days[d]
        if _is_active_status(order.status):
            cell["appointment_count"] += 1
            total_appt += 1
        if _is_verified_status(order.status):
            cell["verified_count"] += 1
            amt = float(item.subtotal or 0)
            cell["verified_amount"] += amt
            total_verified += 1
            total_amount += amt

    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_end_excl - timedelta(days=1)).isoformat(),
        "store_ids": store_ids,
        "days": [days[(week_start + timedelta(days=i)).isoformat()] for i in range(7)],
        "summary": {
            "appointment_count": total_appt,
            "verified_count": total_verified,
            "verified_amount": round(total_amount, 2),
        },
    }


# ─────────────── 月视图（月历） ───────────────

@router.get("/month")
async def get_month_dashboard(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    store_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """月视图月历 — 按日聚合"""
    store_ids = await _resolve_store_ids_for_user(db, current_user, store_id)

    month_start = date(year, month, 1)
    if month == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month + 1, 1)

    stmt = (
        select(OrderItem, UnifiedOrder)
        .join(UnifiedOrder, OrderItem.order_id == UnifiedOrder.id)
        .where(
            OrderItem.appointment_time.is_not(None),
            OrderItem.appointment_time >= datetime.combine(month_start, time(0, 0)),
            OrderItem.appointment_time < datetime.combine(next_month_start, time(0, 0)),
        )
    )
    if store_ids:
        stmt = stmt.where(UnifiedOrder.store_id.in_(store_ids))

    rows = (await db.execute(stmt)).all()

    days_map: Dict[str, Dict[str, Any]] = {}
    for item, order in rows:
        d = item.appointment_time.date().isoformat()
        if d not in days_map:
            days_map[d] = {"date": d, "appointment_count": 0,
                           "verified_count": 0, "verified_amount": 0.0}
        cell = days_map[d]
        if _is_active_status(order.status):
            cell["appointment_count"] += 1
        if _is_verified_status(order.status):
            cell["verified_count"] += 1
            cell["verified_amount"] += float(item.subtotal or 0)

    # 把所有日期补齐
    cur = month_start
    days_list = []
    while cur < next_month_start:
        d = cur.isoformat()
        days_list.append(days_map.get(d, {
            "date": d, "appointment_count": 0,
            "verified_count": 0, "verified_amount": 0.0,
        }))
        cur += timedelta(days=1)

    return {
        "year": year,
        "month": month,
        "store_ids": store_ids,
        "days": days_list,
    }


# ─────────────── 月视图某天订单列表（左右两栏） ───────────────

def _build_order_card(item: OrderItem, order: UnifiedOrder, user_obj: Optional[User]) -> Dict[str, Any]:
    slot = appointment_to_slot(item.appointment_time)
    status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "order_item_id": item.id,
        "appointment_time": item.appointment_time.isoformat() if item.appointment_time else None,
        "slot_no": slot,
        "slot_label": slot_label(slot) if slot else "",
        "customer_name": (user_obj.nickname if user_obj else None) or (user_obj.phone if user_obj else None) or "未知",
        "customer_phone": user_obj.phone if user_obj else None,
        "product_name": item.product_name,
        "amount": float(item.subtotal or 0),
        "status": status_val,
    }


@router.get("/month-day")
async def get_month_day_orders(
    target_date: date = Query(..., alias="date"),
    store_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """月视图：某天订单列表（按上午 / 下午+晚上拆分两列）"""
    store_ids = await _resolve_store_ids_for_user(db, current_user, store_id)

    day_start = datetime.combine(target_date, time(0, 0))
    day_end = day_start + timedelta(days=1)

    stmt = (
        select(OrderItem, UnifiedOrder, User)
        .join(UnifiedOrder, OrderItem.order_id == UnifiedOrder.id)
        .join(User, UnifiedOrder.user_id == User.id)
        .where(
            OrderItem.appointment_time.is_not(None),
            OrderItem.appointment_time >= day_start,
            OrderItem.appointment_time < day_end,
        )
        .order_by(OrderItem.appointment_time.asc())
    )
    if store_ids:
        stmt = stmt.where(UnifiedOrder.store_id.in_(store_ids))

    rows = (await db.execute(stmt)).all()

    morning: List[Dict[str, Any]] = []
    afternoon: List[Dict[str, Any]] = []

    total_appt = total_verified = 0
    total_amount = 0.0

    for item, order, u in rows:
        if not _is_active_status(order.status):
            continue
        card = _build_order_card(item, order, u)
        slot = card["slot_no"]
        if slot is None:
            continue
        # 上午：1-3（06-12）；下午+晚上：4-9（12-24）
        if 1 <= slot <= 3:
            morning.append(card)
        else:
            afternoon.append(card)
        total_appt += 1
        if _is_verified_status(order.status):
            total_verified += 1
            total_amount += float(item.subtotal or 0)

    return {
        "date": target_date.isoformat(),
        "store_ids": store_ids,
        "morning": morning,
        "afternoon": afternoon,
        "summary": {
            "appointment_count": total_appt,
            "verified_count": total_verified,
            "verified_amount": round(total_amount, 2),
        },
    }


# ─────────────── 9 宫格抽屉：某日某时段订单列表 ───────────────

@router.get("/slot/{target_date}/{slot_no}")
async def get_slot_orders(
    target_date: date,
    slot_no: int,
    store_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """9 宫格抽屉：返回指定日期 + 时段的订单列表（操作型 5 字段）"""
    if not 1 <= slot_no <= 9:
        raise HTTPException(status_code=400, detail="slot_no 必须在 1-9 之间")

    store_ids = await _resolve_store_ids_for_user(db, current_user, store_id)
    slot_start, slot_end = slot_window(target_date, slot_no)

    stmt = (
        select(OrderItem, UnifiedOrder, User)
        .join(UnifiedOrder, OrderItem.order_id == UnifiedOrder.id)
        .join(User, UnifiedOrder.user_id == User.id)
        .where(
            OrderItem.appointment_time.is_not(None),
            OrderItem.appointment_time >= slot_start,
            OrderItem.appointment_time < slot_end,
        )
        .order_by(OrderItem.appointment_time.asc())
    )
    if store_ids:
        stmt = stmt.where(UnifiedOrder.store_id.in_(store_ids))

    rows = (await db.execute(stmt)).all()

    orders: List[Dict[str, Any]] = []
    verified_amount = 0.0
    verified_count = 0
    appt_count = 0
    for item, order, u in rows:
        if not _is_active_status(order.status):
            continue
        appt_count += 1
        card = _build_order_card(item, order, u)
        orders.append(card)
        if _is_verified_status(order.status):
            verified_count += 1
            verified_amount += float(item.subtotal or 0)

    return {
        "date": target_date.isoformat(),
        "slot_no": slot_no,
        "slot_label": slot_label(slot_no),
        "store_ids": store_ids,
        "orders": orders,
        "summary": {
            "appointment_count": appt_count,
            "verified_count": verified_count,
            "verified_amount": round(verified_amount, 2),
        },
    }
