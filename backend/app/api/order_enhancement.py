"""[订单系统增强 PRD v1.0] 营业时间窗 / 并发上限 / 时段切片 / 站内消息红点 / 列表附件元信息。

涉及端点：
- POST/GET /api/merchant/business-hours：商家保存/读取营业时间窗（含日期例外）
- POST/GET /api/merchant/concurrency-limit：商家保存/读取并发上限（门店级 + 服务级）
- GET /api/services/{product_id}/available-slots：客户端查询某日可用时段
- GET /api/notifications/unread-count：站内消息红点查询
- POST /api/notifications/mark-read-by-order：按订单粒度标记已读
- POST /api/orders/attachment-meta：批量查询订单的附件元信息
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    MerchantBusinessHours,
    MerchantStore,
    MerchantStoreMembership,
    Notification,
    OrderAttachment,
    OrderItem,
    Product,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
    UserRole,
)
from app.schemas.order_enhancement import (
    ALLOWED_CUTOFF_MINUTES,
    AvailableSlotItem,
    AvailableSlotsResponse,
    BusinessHourEntry,
    BusinessHoursResponse,
    BusinessHoursSaveRequest,
    ConcurrencyLimitSaveRequest,
    MarkReadByOrderRequest,
    OrderAttachmentMeta,
    OrderListAttachmentMetaRequest,
    OrderListAttachmentMetaResponse,
    StoreBookingConfigResponse,
    StoreBookingConfigSaveRequest,
    UnreadCountResponse,
)

logger = logging.getLogger(__name__)


router = APIRouter(tags=["订单系统增强"])


# ──────────────── 工具：商家身份 / 门店权限 ────────────────

async def _user_store_ids(db: AsyncSession, user_id: int) -> List[int]:
    res = await db.execute(
        select(MerchantStoreMembership.store_id).where(MerchantStoreMembership.user_id == user_id)
    )
    return [r[0] for r in res.all()]


async def _ensure_store_permission(
    db: AsyncSession, user: User, store_id: int
) -> None:
    """商家须属于该门店；admin 直接放行。"""
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role == "admin":
        return
    store_ids = await _user_store_ids(db, user.id)
    if store_id not in store_ids:
        raise HTTPException(status_code=403, detail="无该门店权限")


# ──────────────── 1. 商家营业时间窗 ────────────────

@router.post("/api/merchant/business-hours", response_model=BusinessHoursResponse)
async def save_business_hours(
    data: BusinessHoursSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存某门店的营业时间窗（按周 + 日期例外，全量替换）。"""
    await _ensure_store_permission(db, current_user, data.store_id)

    # 校验 entries
    for e in data.entries:
        if e.weekday == -1 and not e.date_exception:
            raise HTTPException(status_code=400, detail="weekday=-1 时必须填 date_exception")
        if e.weekday != -1 and e.date_exception is not None:
            raise HTTPException(status_code=400, detail="weekday!=-1 时不应填 date_exception")
        if e.start_time >= e.end_time and not e.is_closed:
            raise HTTPException(status_code=400, detail="start_time 必须小于 end_time")

    # 全量替换：删除旧记录后插入新记录
    await db.execute(
        MerchantBusinessHours.__table__.delete().where(
            MerchantBusinessHours.store_id == data.store_id
        )
    )

    for e in data.entries:
        db.add(MerchantBusinessHours(
            store_id=data.store_id,
            weekday=e.weekday,
            date_exception=e.date_exception,
            start_time=e.start_time,
            end_time=e.end_time,
            is_closed=e.is_closed,
        ))
    await db.commit()
    return BusinessHoursResponse(store_id=data.store_id, entries=data.entries)


@router.get("/api/merchant/business-hours", response_model=BusinessHoursResponse)
async def get_business_hours(
    store_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_permission(db, current_user, store_id)

    res = await db.execute(
        select(MerchantBusinessHours)
        .where(MerchantBusinessHours.store_id == store_id)
        .order_by(MerchantBusinessHours.weekday, MerchantBusinessHours.start_time)
    )
    rows = res.scalars().all()
    entries = [
        BusinessHourEntry(
            weekday=r.weekday,
            date_exception=r.date_exception,
            start_time=r.start_time,
            end_time=r.end_time,
            is_closed=bool(r.is_closed),
        )
        for r in rows
    ]
    return BusinessHoursResponse(store_id=store_id, entries=entries)


# ──────────────── 2. 并发上限（门店级 + 服务级）────────────────

@router.post("/api/merchant/concurrency-limit")
async def save_concurrency_limit(
    data: ConcurrencyLimitSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-05-05 营业管理入口收敛 PRD v1.0 · N-03]
    门店级唯一字段为 `merchant_stores.slot_capacity`（在「营业管理」页另行保存）。
    本接口的 `store_max_concurrent` 字段不再写库（保留请求字段做双向兼容，避免老前端调用报错），
    仅处理服务级覆盖。
    """
    await _ensure_store_permission(db, current_user, data.store_id)

    # 门店级
    store_res = await db.execute(select(MerchantStore).where(MerchantStore.id == data.store_id))
    store = store_res.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    # [2026-05-05 N-03] 忽略 store_max_concurrent（不再覆盖 slot_capacity）
    # 历史已存在的 slot_capacity 值仅由「营业管理」页面或编辑门店页负责维护

    # 服务级
    if data.service_overrides:
        for ov in data.service_overrides:
            p_res = await db.execute(select(Product).where(Product.id == ov.product_id))
            product = p_res.scalar_one_or_none()
            if not product:
                continue
            product.max_concurrent_override = ov.max_concurrent_override
            if ov.service_duration_minutes is not None:
                product.service_duration_minutes = ov.service_duration_minutes

    await db.commit()
    return {"message": "已保存"}


@router.get("/api/merchant/concurrency-limit")
async def get_concurrency_limit(
    store_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_permission(db, current_user, store_id)

    store_res = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = store_res.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")

    # 该门店挂的服务（通过 ProductStore 关联）
    from app.models.models import ProductStore  # 局部导入避免循环
    res = await db.execute(
        select(Product)
        .join(ProductStore, ProductStore.product_id == Product.id)
        .where(ProductStore.store_id == store_id)
    )
    products = res.scalars().all()
    services = [
        {
            "product_id": p.id,
            "name": p.name,
            "max_concurrent_override": p.max_concurrent_override,
            "service_duration_minutes": p.service_duration_minutes,
            "effective_max_concurrent": (
                p.max_concurrent_override if p.max_concurrent_override is not None else store.slot_capacity
            ),
        }
        for p in products
    ]

    return {
        "store_id": store_id,
        "store_max_concurrent": store.slot_capacity or 1,
        "services": services,
    }


# ──────────────── 2.5 门店「营业管理」booking-config（slot_capacity / advance_days / booking_cutoff_minutes） ────────────────
# [2026-05-05 营业管理入口收敛 PRD v1.0 · N-02 / N-05 / N-06]

@router.get(
    "/api/merchant/stores/{store_id}/booking-config",
    response_model=StoreBookingConfigResponse,
)
async def get_store_booking_config(
    store_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """营业管理页聚合返回：门店总接待名额 + 门店级 advance_days + 门店级 booking_cutoff_minutes。"""
    await _ensure_store_permission(db, current_user, store_id)
    res = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = res.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    return StoreBookingConfigResponse(
        store_id=store.id,
        slot_capacity=int(store.slot_capacity or 0),
        advance_days=getattr(store, "advance_days", None),
        booking_cutoff_minutes=getattr(store, "booking_cutoff_minutes", None),
    )


@router.put("/api/merchant/stores/{store_id}/booking-config")
async def update_store_booking_config(
    store_id: int,
    data: StoreBookingConfigSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """营业管理页保存：门店总接待名额 + 门店级 advance_days + 门店级 booking_cutoff_minutes。"""
    await _ensure_store_permission(db, current_user, store_id)
    # 取值校验：booking_cutoff_minutes 必须在枚举中
    if data.booking_cutoff_minutes is not None and data.booking_cutoff_minutes not in ALLOWED_CUTOFF_MINUTES:
        raise HTTPException(
            status_code=400,
            detail="booking_cutoff_minutes 取值非法，仅允许：null/0/15/30/60/120/720/1440",
        )
    res = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = res.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    store.slot_capacity = int(data.slot_capacity or 0)
    store.advance_days = data.advance_days
    store.booking_cutoff_minutes = data.booking_cutoff_minutes
    await db.commit()
    return {"message": "已保存"}


# ──────────────── 3. 时段切片查询 ────────────────

def _hhmm_to_minutes(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _minutes_to_time(minutes: int) -> time:
    h, m = divmod(minutes, 60)
    return time(hour=h % 24, minute=m)


async def _get_business_windows(
    db: AsyncSession, store_id: int, target_date: date
) -> List[Tuple[int, int]]:
    """返回某日的营业时间窗列表（按分钟）：[(start_min, end_min), ...]。

    优先级：date_exception > weekday；如果某日有 is_closed 例外，则视为休息。
    若无任何 business_hours 记录，回退到 MerchantStore.business_start/business_end。
    """
    # 查 date_exception
    res_exc = await db.execute(
        select(MerchantBusinessHours).where(
            MerchantBusinessHours.store_id == store_id,
            MerchantBusinessHours.weekday == -1,
            MerchantBusinessHours.date_exception == target_date,
        )
    )
    exc = res_exc.scalars().all()
    if exc:
        if any(e.is_closed for e in exc):
            return []
        return [(_hhmm_to_minutes(e.start_time), _hhmm_to_minutes(e.end_time)) for e in exc]

    # 查 weekday：date.weekday() 0=周一...6=周日，正好对齐
    weekday = target_date.weekday()
    res_wk = await db.execute(
        select(MerchantBusinessHours).where(
            MerchantBusinessHours.store_id == store_id,
            MerchantBusinessHours.weekday == weekday,
        )
    )
    wk = res_wk.scalars().all()
    if wk:
        return [(_hhmm_to_minutes(e.start_time), _hhmm_to_minutes(e.end_time)) for e in wk]

    # 回退到 MerchantStore.business_start/business_end
    res_store = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = res_store.scalar_one_or_none()
    if store and store.business_start and store.business_end:
        try:
            return [(_hhmm_to_minutes(store.business_start), _hhmm_to_minutes(store.business_end))]
        except Exception:  # noqa: BLE001
            return []

    # 默认 09:00 ~ 18:00
    return [(9 * 60, 18 * 60)]


_OCCUPIED_STATUSES = (
    UnifiedOrderStatus.pending_payment,
    UnifiedOrderStatus.pending_appointment,
    UnifiedOrderStatus.appointed,
    UnifiedOrderStatus.pending_use,
    UnifiedOrderStatus.partial_used,
)


async def _count_occupancy(
    db: AsyncSession,
    *,
    store_id: int,
    product_id: Optional[int],
    slot_start: datetime,
    slot_end: datetime,
) -> int:
    """统计某时段（slot_start, slot_end）的占用订单数。

    时段重叠条件：appointment_time 落在 [slot_start, slot_end) 区间。
    考虑兼容历史：仅按 OrderItem.appointment_time 判定，不严格判 end_time。
    """
    q = (
        select(func.count(UnifiedOrder.id.distinct()))
        .select_from(UnifiedOrder)
        .join(OrderItem, OrderItem.order_id == UnifiedOrder.id)
        .where(
            UnifiedOrder.store_id == store_id,
            UnifiedOrder.status.in_(_OCCUPIED_STATUSES),
            OrderItem.appointment_time >= slot_start,
            OrderItem.appointment_time < slot_end,
        )
    )
    if product_id is not None:
        q = q.where(OrderItem.product_id == product_id)

    res = await db.execute(q)
    return int(res.scalar() or 0)


@router.get("/api/services/{product_id}/available-slots", response_model=AvailableSlotsResponse)
async def get_available_slots(
    product_id: int,
    target_date: date = Query(..., alias="date"),
    store_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询某商品某日可用时段。

    - 营业时间外：完全不展示
    - 已占用（达到上限）：展示但 is_available=False，reason=occupied
    - 当天最小提前 30 分钟：reason=past
    """
    p_res = await db.execute(select(Product).where(Product.id == product_id))
    product = p_res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    duration = product.service_duration_minutes or 60

    # 解析门店（缺省取关联的第一家）
    if store_id is None:
        from app.models.models import ProductStore  # 局部导入
        ps_res = await db.execute(
            select(ProductStore.store_id).where(ProductStore.product_id == product_id).limit(1)
        )
        row = ps_res.first()
        if row:
            store_id = row[0]
    if store_id is None:
        raise HTTPException(status_code=400, detail="无法确定门店")

    store_res = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = store_res.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")

    store_cap = max(1, int(store.slot_capacity or 1))
    service_cap = product.max_concurrent_override if product.max_concurrent_override is not None else store_cap

    windows = await _get_business_windows(db, store_id, target_date)

    now = datetime.utcnow() + timedelta(hours=8)  # 转 Asia/Shanghai 简化

    # [2026-05-05 营业管理入口收敛 PRD v1.0 · N-06] 双层「当日截止」兜底：
    # 商品级 booking_cutoff_minutes 优先 → 门店级 booking_cutoff_minutes 兜底 → 系统默认 30 分钟。
    # 取值校验：枚举 {None, 0(=不限制), 15, 30, 60, 120, 720, 1440}；其它非法值视为 None 后兜底。
    _ALLOWED_CUTOFF = {0, 15, 30, 60, 120, 720, 1440}
    p_cut = getattr(product, "booking_cutoff_minutes", None)
    s_cut = getattr(store, "booking_cutoff_minutes", None)
    if p_cut is not None and p_cut not in _ALLOWED_CUTOFF:
        p_cut = None
    if s_cut is not None and s_cut not in _ALLOWED_CUTOFF:
        s_cut = None
    if p_cut is not None:
        min_advance_min = int(p_cut)
    elif s_cut is not None:
        min_advance_min = int(s_cut)
    else:
        min_advance_min = 30

    slots: List[AvailableSlotItem] = []
    for (win_start, win_end) in windows:
        cur = win_start
        # 末端处理：cur + duration 必须 <= win_end
        while cur + duration <= win_end:
            slot_start_dt = datetime.combine(target_date, _minutes_to_time(cur))
            slot_end_dt = slot_start_dt + timedelta(minutes=duration)

            reason: Optional[str] = None
            available = True

            # 当天最小提前（仅当日生效；min_advance_min=0 表示不限制）
            if target_date == now.date() and min_advance_min > 0:
                if slot_start_dt - timedelta(minutes=min_advance_min) < now.replace(tzinfo=None):
                    available = False
                    reason = "past"

            if available:
                # 双层并发判定
                concurrent_service = await _count_occupancy(
                    db, store_id=store_id, product_id=product_id,
                    slot_start=slot_start_dt, slot_end=slot_end_dt,
                )
                concurrent_store = await _count_occupancy(
                    db, store_id=store_id, product_id=None,
                    slot_start=slot_start_dt, slot_end=slot_end_dt,
                )
                if concurrent_service >= service_cap or concurrent_store >= store_cap:
                    available = False
                    reason = "occupied"

            # 营业时段外的不展示（仅展示窗口内的切片，已在 while 中保证）
            if available or reason in ("occupied", "past"):
                slots.append(AvailableSlotItem(
                    start_at=slot_start_dt,
                    end_at=slot_end_dt,
                    is_available=available,
                    reason=reason,
                ))
            cur += duration

    return AvailableSlotsResponse(
        product_id=product_id,
        store_id=store_id,
        duration_minutes=duration,
        date=target_date,
        slots=slots,
    )


# ──────────────── 4. 站内消息红点 ────────────────

@router.get("/api/notifications/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """红点查询：返回未读总数 + 有未读消息的订单 ID 列表。"""
    res_total = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    total_unread = int(res_total.scalar() or 0)

    res_orders = await db.execute(
        select(Notification.order_id)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.order_id.isnot(None),
        )
        .distinct()
    )
    order_ids = [r[0] for r in res_orders.all() if r[0] is not None]

    return UnreadCountResponse(
        total_unread=total_unread,
        total_orders_with_unread=len(order_ids),
        order_ids=order_ids,
    )


@router.post("/api/notifications/mark-read-by-order")
async def mark_read_by_order(
    data: MarkReadByOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按订单粒度清除红点：将该订单下当前用户的所有未读站内信标记为已读。"""
    now = datetime.utcnow()
    res = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.order_id == data.order_id,
            Notification.is_read == False,
        )
        .values(is_read=True, read_at=now)
    )
    await db.commit()
    return {"message": "已标记已读", "affected": res.rowcount or 0}


# ──────────────── 5. 订单列表附件元信息 ────────────────

@router.post("/api/orders/attachment-meta", response_model=OrderListAttachmentMetaResponse)
async def get_order_attachment_meta(
    data: OrderListAttachmentMetaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量查询订单的附件元信息（供"我的订单"列表用）。

    输入：order_ids（item 模式时为 OrderItem.id；unified 模式时为 UnifiedOrder.id 但本期不展开）
    输出：每个订单的图片数、PDF 数、前 3 张图片缩略图 URL
    """
    # 安全过滤：只能查自己的订单
    if data.order_source == "item":
        # 校验所有 order_ids 都属于当前用户
        res_check = await db.execute(
            select(OrderItem.id)
            .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
            .where(
                OrderItem.id.in_(data.order_ids),
                UnifiedOrder.user_id == current_user.id,
            )
        )
        valid_ids = {r[0] for r in res_check.all()}
        order_ids = [i for i in data.order_ids if i in valid_ids]
    else:
        res_check = await db.execute(
            select(UnifiedOrder.id).where(
                UnifiedOrder.id.in_(data.order_ids),
                UnifiedOrder.user_id == current_user.id,
            )
        )
        valid_ids = {r[0] for r in res_check.all()}
        order_ids = [i for i in data.order_ids if i in valid_ids]

    if not order_ids:
        return OrderListAttachmentMetaResponse(items=[])

    res = await db.execute(
        select(OrderAttachment)
        .where(
            OrderAttachment.order_id.in_(order_ids),
            OrderAttachment.order_source == data.order_source,
            OrderAttachment.deleted_at.is_(None),
        )
        .order_by(OrderAttachment.created_at.asc())
    )
    rows = res.scalars().all()

    metas: Dict[int, OrderAttachmentMeta] = {
        oid: OrderAttachmentMeta(order_id=oid) for oid in order_ids
    }
    for att in rows:
        m = metas[att.order_id]
        if att.file_type == "image":
            m.image_count += 1
            if len(m.image_thumbs) < 3:
                m.image_thumbs.append(att.thumbnail_url or att.file_url)
        elif att.file_type == "pdf":
            m.pdf_count += 1
        m.total_count += 1

    items = [m for m in metas.values() if m.total_count > 0]
    return OrderListAttachmentMetaResponse(items=items)
