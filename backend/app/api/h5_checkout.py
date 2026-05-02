"""H5 下单流程优化 PRD v1.0（2026-05-02）：支付页统一选择相关接口。

- GET  /api/h5/checkout/init  返回支付页所需的日期范围、默认门店、联系人手机号等
- GET  /api/h5/slots          返回某门店某日期下的可用时段（商品时段 ∩ 门店营业时段，且排除已满档）

满档判定：`(门店, 日期, 时段)` 当前占用 < 门店 `slot_capacity`（默认 10）。
占用数 = 已支付 + 待支付（创建后 15 分钟内未取消未超时）。
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    MerchantStore,
    OrderItem,
    Product,
    ProductStore,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)

router = APIRouter(prefix="/api/h5", tags=["H5 下单流程"])


# ---------------- 工具函数 ----------------


def _compute_date_range(advance_days: int, include_today: bool) -> tuple[date, date]:
    """计算可预约日期区间。

    include_today=True  → [today, today + N - 1]
    include_today=False → [today + 1, today + N]
    """
    n = max(1, int(advance_days or 1))
    if include_today:
        start = date.today()
    else:
        start = date.today() + timedelta(days=1)
    end = start + timedelta(days=n - 1)
    return start, end


def _slot_in_business_hours(
    slot_start: str, slot_end: str, biz_start: Optional[str], biz_end: Optional[str]
) -> bool:
    """商品时段必须完全落在门店营业时段之内才纳入候选。空营业时段视为全天可用。"""
    if not biz_start or not biz_end:
        return True
    try:
        return slot_start >= biz_start and slot_end <= biz_end
    except Exception:
        return True


async def _count_occupied(
    db: AsyncSession,
    store_id: int,
    product_id: int,
    target_date: date,
    slot_label: str,
) -> int:
    """[H5 下单流程优化 PRD v1.0] 占用数 = 已支付 + 待支付（15 分钟内未取消未超时）。

    口径：`UnifiedOrder.status` 为 `pending_shipment / pending_receipt /
    pending_use / pending_review / completed` 视为已支付；
    `pending_payment` 且 `created_at > NOW() - 15min` 视为待支付占用。
    """
    fifteen_min_ago = datetime.utcnow() - timedelta(minutes=15)

    paid_like = [
        UnifiedOrderStatus.pending_shipment,
        UnifiedOrderStatus.pending_receipt,
        UnifiedOrderStatus.pending_use,
        UnifiedOrderStatus.pending_review,
        UnifiedOrderStatus.completed,
    ]

    q = (
        select(func.count(OrderItem.id))
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            OrderItem.product_id == product_id,
            func.date(OrderItem.appointment_time) == target_date,
            func.json_extract(OrderItem.appointment_data, "$.time_slot") == slot_label,
            UnifiedOrder.store_id == store_id,
            (
                (UnifiedOrder.status.in_(paid_like))
                | (
                    (UnifiedOrder.status == UnifiedOrderStatus.pending_payment)
                    & (UnifiedOrder.created_at >= fifteen_min_ago)
                )
            ),
        )
    )
    res = await db.execute(q)
    return int(res.scalar() or 0)


# ---------------- /api/h5/checkout/init ----------------


@router.get("/checkout/init")
async def checkout_init(
    productId: int = Query(..., description="商品 ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """支付页打开时调用：返回支付页所需的日期范围、默认门店、联系人手机号。"""
    p_res = await db.execute(select(Product).where(Product.id == productId))
    product = p_res.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    advance_days = int(getattr(product, "advance_days", 0) or 0)
    include_today = getattr(product, "include_today", True)
    if include_today is None:
        include_today = True

    if advance_days > 0:
        start, end = _compute_date_range(advance_days, bool(include_today))
        date_range = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "include_today": bool(include_today),
            "advance_days": advance_days,
        }
    else:
        # 不需要预约或未配置 advance_days 时，给一个空结构，前端按需处理
        date_range = {
            "start": None,
            "end": None,
            "include_today": bool(include_today),
            "advance_days": 0,
        }

    # 默认门店：取商品绑定的第一个 active 门店
    store_q = await db.execute(
        select(MerchantStore)
        .join(ProductStore, ProductStore.store_id == MerchantStore.id)
        .where(ProductStore.product_id == productId, MerchantStore.status == "active")
        .order_by(MerchantStore.id.asc())
    )
    default_store_obj = store_q.scalars().first()
    default_store = None
    if default_store_obj:
        default_store = {
            "id": default_store_obj.id,
            "store_id": default_store_obj.id,
            "name": default_store_obj.store_name,
            "address": default_store_obj.address,
            "lat": float(default_store_obj.lat) if default_store_obj.lat is not None else None,
            "lng": float(default_store_obj.lng) if default_store_obj.lng is not None else None,
            "slot_capacity": getattr(default_store_obj, "slot_capacity", 10) or 10,
            "business_start": getattr(default_store_obj, "business_start", None),
            "business_end": getattr(default_store_obj, "business_end", None),
        }

    contact_phone = getattr(current_user, "phone", None) or ""

    # 商品时段（前端隐藏 capacity，仅用于展示）
    available_slots = []
    for slot in (product.time_slots or []):
        available_slots.append({
            "start": slot.get("start", ""),
            "end": slot.get("end", ""),
        })

    return {
        "code": 0,
        "data": {
            "product_id": productId,
            "appointment_mode": (
                product.appointment_mode.value
                if hasattr(product.appointment_mode, "value")
                else (product.appointment_mode or "none")
            ),
            "date_range": date_range,
            "available_slots": available_slots,
            "default_store": default_store,
            "contact_phone": contact_phone,
        },
    }


# ---------------- /api/h5/slots ----------------


@router.get("/slots")
async def get_slots(
    storeId: int = Query(..., description="门店 ID"),
    date_str: str = Query(..., alias="date", description="查询日期 YYYY-MM-DD"),
    productId: int = Query(..., description="商品 ID"),
    db: AsyncSession = Depends(get_db),
):
    """返回该门店该日期下的可用时段（商品时段 ∩ 门店营业时段 + 排除已满档）。"""
    try:
        q_date = date.fromisoformat(date_str)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    p_res = await db.execute(select(Product).where(Product.id == productId))
    product = p_res.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    s_res = await db.execute(select(MerchantStore).where(MerchantStore.id == storeId))
    store = s_res.scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="门店不存在")

    biz_start = getattr(store, "business_start", None)
    biz_end = getattr(store, "business_end", None)
    capacity = int(getattr(store, "slot_capacity", 10) or 10)

    product_slots: List[dict] = product.time_slots or []
    items: List[dict] = []
    for slot in product_slots:
        s_start = slot.get("start", "")
        s_end = slot.get("end", "")
        if not s_start or not s_end:
            continue
        # 1) 商品时段 ∩ 门店营业时段
        if not _slot_in_business_hours(s_start, s_end, biz_start, biz_end):
            continue
        slot_label = f"{s_start}-{s_end}"
        # 2) 满档判定（排除已满档）
        occupied = await _count_occupied(db, storeId, productId, q_date, slot_label)
        full = occupied >= capacity
        if full:
            # 列表中**直接隐藏**已满时段（PRD §4.4）
            continue
        items.append({
            "start": s_start,
            "end": s_end,
            "label": slot_label,
            "occupied": occupied,
            "capacity": capacity,
            "available": max(0, capacity - occupied),
        })

    return {
        "code": 0,
        "data": {
            "store_id": storeId,
            "date": date_str,
            "slots": items,
            "business_start": biz_start,
            "business_end": biz_end,
            "slot_capacity": capacity,
        },
    }
