"""H5 下单流程优化 PRD v1.0（2026-05-02）：支付页统一选择相关接口。

- GET  /api/h5/checkout/init  返回支付页所需的日期范围、默认门店、联系人手机号等
- GET  /api/h5/slots          返回某门店某日期下的可用时段（商品时段 ∩ 门店营业时段）
- GET  /api/h5/checkout/info  [PRD v1.0 2026-05-04]
        统一返回下单页所需的全部数据，时段/日期均带 `is_available` +
        `unavailable_reason` 字段，前端可据此置灰展示满额项。

满档判定（双层）：
- 商品级：`product.time_slots[i].capacity` 未填或 = 0 视为不限制；
- 门店级：`store.slot_capacity` 默认 10，跨商品累计；
- 占用数 = 已支付（pending_shipment / pending_receipt / pending_use /
          partial_used / pending_review / completed） +
          待支付（pending_payment 且 created_at 在 15 分钟内）。

[PRD 2026-05-04 §5.2 下单页时段卡片「已满/已结束」角标改造]
- 时段对象新增 `status` 枚举字段，三态：`available` / `full` / `ended`
- 派生规则：
    unavailable_reason == 'past'     → status = 'ended'
    unavailable_reason == 'occupied' → status = 'full'
    is_available == True             → status = 'available'
- 前端按 `status` 驱动橙色贴边小色块角标：`full → 已满`、`ended → 已结束`、`available → 不显示角标`
- 同一时段既 ended 又 full 时，按 PRD §5.1「已结束优先」显示 `ended`（代码中优先判定过期再判满额）。
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


def _resolve_effective_advance_days(product, store) -> int:
    """[2026-05-05 营业管理入口收敛 PRD v1.0 · N-05] 双层兜底取值：

    商品级 advance_days（>0）优先 → 门店级 advance_days（>0）兜底 → 0=不限制。
    """
    p_val = getattr(product, "advance_days", None)
    if p_val is not None and int(p_val) > 0:
        return int(p_val)
    s_val = getattr(store, "advance_days", None) if store is not None else None
    if s_val is not None and int(s_val) > 0:
        return int(s_val)
    return 0


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


# [PRD 2026-05-04 §5.2 角标改造] 时段状态派生工具函数
def _derive_slot_status(is_available: bool, unavailable_reason: Optional[str]) -> str:
    """根据 is_available + unavailable_reason 派生出统一的 `status` 枚举。

    三态：`available` / `full` / `ended`。PRD §5.1 规定：同时满足已结束与已满时按
    「已结束」优先，调用方在上游已按「先判 past 再判 occupied」的顺序组装，
    因此本函数只做单字段映射。
    """
    if is_available:
        return "available"
    if unavailable_reason == "past":
        return "ended"
    if unavailable_reason == "occupied":
        return "full"
    # 其它未知原因降级为 full（保守策略：展示橙色「已满」角标）
    return "full"


# [PRD v1.0 2026-05-04] 已支付状态集（用于占用判定）
_PAID_LIKE_STATUSES = [
    UnifiedOrderStatus.pending_shipment,
    UnifiedOrderStatus.pending_receipt,
    UnifiedOrderStatus.pending_use,
    UnifiedOrderStatus.pending_review,
    UnifiedOrderStatus.completed,
]


async def _count_occupied(
    db: AsyncSession,
    store_id: int,
    product_id: int,
    target_date: date,
    slot_label: str,
) -> int:
    """[H5 下单流程优化 PRD v1.0] 占用数 = 已支付 + 待支付（PAYMENT_TIMEOUT_MINUTES 内未取消未超时）。

    口径：`UnifiedOrder.status` 为 `pending_shipment / pending_receipt /
    pending_use / pending_review / completed` 视为已支付；
    `pending_payment` 且 `created_at > NOW() - PAYMENT_TIMEOUT_MINUTES` 视为待支付占用。

    [订单核销码状态与未支付超时治理 v1.0] 此处的"15 分钟"硬编码
    已改为读取全局 `settings.PAYMENT_TIMEOUT_MINUTES`，与"未支付超时
    自动取消"定时任务的判定阈值长期保持一致。
    """
    from app.core.config import settings
    timeout_minutes = int(getattr(settings, "PAYMENT_TIMEOUT_MINUTES", 15) or 15)
    pending_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)

    q = (
        select(func.count(OrderItem.id))
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            OrderItem.product_id == product_id,
            func.date(OrderItem.appointment_time) == target_date,
            func.json_extract(OrderItem.appointment_data, "$.time_slot") == slot_label,
            UnifiedOrder.store_id == store_id,
            (
                (UnifiedOrder.status.in_(_PAID_LIKE_STATUSES))
                | (
                    (UnifiedOrder.status == UnifiedOrderStatus.pending_payment)
                    & (UnifiedOrder.created_at >= pending_threshold)
                )
            ),
        )
    )
    res = await db.execute(q)
    return int(res.scalar() or 0)


async def _count_occupied_store(
    db: AsyncSession,
    store_id: int,
    target_date: date,
    slot_label: str,
) -> int:
    """[PRD v1.0 2026-05-04 §5.1] 门店级时段占用数（跨商品累计）。

    与 `_count_occupied` 相同口径，但**不限定商品**——`store.slot_capacity`
    是「该门店该时段所有商品订单累计上限」。

    [订单核销码状态与未支付超时治理 v1.0] 同步改为读全局 PAYMENT_TIMEOUT_MINUTES。
    """
    from app.core.config import settings
    timeout_minutes = int(getattr(settings, "PAYMENT_TIMEOUT_MINUTES", 15) or 15)
    pending_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    q = (
        select(func.count(OrderItem.id))
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            func.date(OrderItem.appointment_time) == target_date,
            func.json_extract(OrderItem.appointment_data, "$.time_slot") == slot_label,
            UnifiedOrder.store_id == store_id,
            (
                (UnifiedOrder.status.in_(_PAID_LIKE_STATUSES))
                | (
                    (UnifiedOrder.status == UnifiedOrderStatus.pending_payment)
                    & (UnifiedOrder.created_at >= pending_threshold)
                )
            ),
        )
    )
    res = await db.execute(q)
    return int(res.scalar() or 0)


async def _count_occupied_date(
    db: AsyncSession,
    store_id: int,
    product_id: Optional[int],
    target_date: date,
) -> int:
    """[PRD v1.0 2026-05-04 §5.2] 按日期汇总占用数（date 模式用）。

    `product_id is None` → 门店级聚合（跨商品累计）；否则商品级。

    [订单核销码状态与未支付超时治理 v1.0] 同步改为读全局 PAYMENT_TIMEOUT_MINUTES。
    """
    from app.core.config import settings
    timeout_minutes = int(getattr(settings, "PAYMENT_TIMEOUT_MINUTES", 15) or 15)
    pending_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    q = (
        select(func.count(OrderItem.id))
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            func.date(OrderItem.appointment_time) == target_date,
            UnifiedOrder.store_id == store_id,
            (
                (UnifiedOrder.status.in_(_PAID_LIKE_STATUSES))
                | (
                    (UnifiedOrder.status == UnifiedOrderStatus.pending_payment)
                    & (UnifiedOrder.created_at >= pending_threshold)
                )
            ),
        )
    )
    if product_id is not None:
        q = q.where(OrderItem.product_id == product_id)
    res = await db.execute(q)
    return int(res.scalar() or 0)


def _slot_capacity_for(product, slot_dict: dict) -> int:
    """[PRD v1.0 2026-05-04 §5.4] 商品级时段容量。

    未填或 = 0 视为「商品级不限制」，返回 0 表示无上限。
    """
    cap = slot_dict.get("capacity") if isinstance(slot_dict, dict) else None
    try:
        cap = int(cap or 0)
    except (TypeError, ValueError):
        cap = 0
    return max(0, cap)


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

    # [2026-05-05 N-05] 先确定默认门店，再用「商品级优先、门店级兜底」算 advance_days
    store_q = await db.execute(
        select(MerchantStore)
        .join(ProductStore, ProductStore.store_id == MerchantStore.id)
        .where(ProductStore.product_id == productId, MerchantStore.status == "active")
        .order_by(MerchantStore.id.asc())
    )
    default_store_obj = store_q.scalars().first()

    include_today = getattr(product, "include_today", True)
    if include_today is None:
        include_today = True

    advance_days = _resolve_effective_advance_days(product, default_store_obj)
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
    # [PRD v1.0 2026-05-04 §5.1] 双层判定：商品级 capacity（每个 slot 独立）
    # + 门店级 slot_capacity（跨商品累计，门店容量为 0 时不限制）。
    # 满额时段不再过滤，而是返回 is_available=false + reason=occupied，前端置灰展示。
    for slot in product_slots:
        s_start = slot.get("start", "")
        s_end = slot.get("end", "")
        if not s_start or not s_end:
            continue
        # 1) 商品时段 ∩ 门店营业时段
        if not _slot_in_business_hours(s_start, s_end, biz_start, biz_end):
            continue
        slot_label = f"{s_start}-{s_end}"
        product_cap = _slot_capacity_for(product, slot)
        product_occupied = await _count_occupied(db, storeId, productId, q_date, slot_label)
        product_full = product_cap > 0 and product_occupied >= product_cap

        store_full = False
        store_occupied = 0
        if capacity > 0:
            store_occupied = await _count_occupied_store(db, storeId, q_date, slot_label)
            store_full = store_occupied >= capacity

        # [PRD 2026-05-04 §5.1 「已结束」优先] 当天且 slot 结束时间 <= 现在 → 已结束，覆盖 occupied
        is_ended = False
        try:
            if q_date == date.today() and s_end <= datetime.now().strftime("%H:%M"):
                is_ended = True
        except Exception:
            is_ended = False

        is_available = not (product_full or store_full or is_ended)
        if is_ended:
            unavailable_reason = "past"
        elif not is_available:
            unavailable_reason = "occupied"
        else:
            unavailable_reason = None

        items.append({
            "start": s_start,
            "end": s_end,
            "label": slot_label,
            # 兼容字段：旧前端使用 occupied/available 计算
            "occupied": product_occupied,
            "capacity": capacity,
            "available": max(0, capacity - max(product_occupied, store_occupied)) if capacity > 0 else 9999,
            # [PRD v1.0 2026-05-04 §6.2] 既有字段
            "is_available": is_available,
            "unavailable_reason": unavailable_reason,
            # [PRD 2026-05-04 §5.2 角标改造] 新增 status 枚举字段
            "status": _derive_slot_status(is_available, unavailable_reason),
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


# ---------------- /api/h5/checkout/info ----------------


@router.get("/checkout/info")
async def checkout_info(
    productId: int = Query(..., description="商品 ID"),
    storeId: Optional[int] = Query(None, description="门店 ID，缺省取商品绑定的第一个 active 门店"),
    date_str: Optional[str] = Query(None, alias="date", description="time_slot 模式查询此日期下的时段（默认 date_range.start）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD v1.0 2026-05-04] 用户端下单页统一信息接口（H5/小程序/Flutter 共用）。

    返回字段在 `init` 基础上扩展：
      - `available_slots`：每个时段附带 `is_available` + `unavailable_reason`（time_slot 模式）
      - `available_dates`：日期级满额信息（date 模式）
    """
    # 1) 商品基础信息
    p_res = await db.execute(select(Product).where(Product.id == productId))
    product = p_res.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    appointment_mode = (
        product.appointment_mode.value
        if hasattr(product.appointment_mode, "value")
        else (product.appointment_mode or "none")
    )

    # 3) 默认门店（若调用方未指定 storeId）
    default_store_obj = None
    if storeId is None:
        store_q = await db.execute(
            select(MerchantStore)
            .join(ProductStore, ProductStore.store_id == MerchantStore.id)
            .where(ProductStore.product_id == productId, MerchantStore.status == "active")
            .order_by(MerchantStore.id.asc())
        )
        default_store_obj = store_q.scalars().first()
        if default_store_obj is not None:
            storeId = default_store_obj.id
    else:
        s_res = await db.execute(select(MerchantStore).where(MerchantStore.id == storeId))
        default_store_obj = s_res.scalar_one_or_none()

    # 2) 日期范围（先确定门店，再做商品级优先、门店级兜底的 advance_days 取值）
    include_today = getattr(product, "include_today", True)
    if include_today is None:
        include_today = True
    advance_days = _resolve_effective_advance_days(product, default_store_obj)
    if advance_days > 0:
        d_start, d_end = _compute_date_range(advance_days, bool(include_today))
        date_range = {
            "start": d_start.isoformat(),
            "end": d_end.isoformat(),
            "include_today": bool(include_today),
            "advance_days": advance_days,
        }
    else:
        d_start, d_end = None, None
        date_range = {
            "start": None,
            "end": None,
            "include_today": bool(include_today),
            "advance_days": 0,
        }

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

    biz_start = getattr(default_store_obj, "business_start", None) if default_store_obj else None
    biz_end = getattr(default_store_obj, "business_end", None) if default_store_obj else None
    store_capacity = int(getattr(default_store_obj, "slot_capacity", 0) or 0) if default_store_obj else 0

    # 4) target_date：时段满额查询所用的日期
    target_date: Optional[date] = None
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    elif d_start is not None:
        target_date = d_start

    # 5) available_slots（time_slot 模式带满额）
    available_slots: List[dict] = []
    if appointment_mode == "time_slot":
        product_slots: List[dict] = product.time_slots or []
        today = date.today()
        now = datetime.now()
        now_hm = now.strftime("%H:%M")
        for slot in product_slots:
            s_start = slot.get("start", "")
            s_end = slot.get("end", "")
            if not s_start or not s_end:
                continue
            slot_label = f"{s_start}-{s_end}"
            # 营业时段过滤（门店不可用 / 不在营业时段：直接 skip 不展示，因为不在该门店候选范围）
            if default_store_obj and not _slot_in_business_hours(s_start, s_end, biz_start, biz_end):
                continue
            is_available = True
            unavailable_reason: Optional[str] = None
            # 当天 + 已过期
            if target_date is not None and target_date == today and s_end <= now_hm:
                is_available = False
                unavailable_reason = "past"
            # 满额判定（双层）
            if is_available and target_date is not None and storeId is not None:
                product_cap = _slot_capacity_for(product, slot)
                product_occupied = 0
                if product_cap > 0:
                    product_occupied = await _count_occupied(
                        db, storeId, productId, target_date, slot_label,
                    )
                product_full = product_cap > 0 and product_occupied >= product_cap

                store_full = False
                if store_capacity > 0:
                    store_occupied = await _count_occupied_store(
                        db, storeId, target_date, slot_label,
                    )
                    store_full = store_occupied >= store_capacity

                if product_full or store_full:
                    is_available = False
                    unavailable_reason = "occupied"

            available_slots.append({
                "start_time": s_start,
                "end_time": s_end,
                # 历史兼容字段
                "start": s_start,
                "end": s_end,
                "label": slot_label,
                "is_available": is_available,
                "unavailable_reason": unavailable_reason,
                # [PRD 2026-05-04 §5.2 角标改造] 新增 status 枚举字段
                "status": _derive_slot_status(is_available, unavailable_reason),
            })

    # 6) available_dates（date 模式带满额）
    available_dates: List[dict] = []
    if appointment_mode == "date" and d_start is not None and d_end is not None:
        today = date.today()
        cur = d_start
        while cur <= d_end:
            is_available = True
            unavailable_reason: Optional[str] = None
            if cur < today:
                is_available = False
                unavailable_reason = "past"
            else:
                # 商品级 daily_quota
                daily_quota = int(getattr(product, "daily_quota", 0) or 0)
                product_full = False
                if daily_quota > 0 and storeId is not None:
                    product_date_occupied = await _count_occupied_date(
                        db, storeId, productId, cur,
                    )
                    product_full = product_date_occupied >= daily_quota
                # 门店级 slot_capacity（用于 date 模式时按"门店日并发"使用）
                store_full = False
                if store_capacity > 0 and storeId is not None:
                    store_date_occupied = await _count_occupied_date(
                        db, storeId, None, cur,
                    )
                    store_full = store_date_occupied >= store_capacity
                if product_full or store_full:
                    is_available = False
                    unavailable_reason = "occupied"
            available_dates.append({
                "date": cur.isoformat(),
                "is_available": is_available,
                "unavailable_reason": unavailable_reason,
                # [PRD 2026-05-04 §5.2 角标改造] 日期也派生 status，便于前端统一处理
                "status": _derive_slot_status(is_available, unavailable_reason),
            })
            cur = cur + timedelta(days=1)

    contact_phone = getattr(current_user, "phone", None) or ""

    return {
        "code": 0,
        "data": {
            "product_id": productId,
            "appointment_mode": appointment_mode,
            "date_range": date_range,
            "default_store": default_store,
            "available_slots": available_slots,
            "available_dates": available_dates,
            "contact_phone": contact_phone,
        },
    }
