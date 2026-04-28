from calendar import monthrange
from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_identity
from app.models.models import (
    MerchantMemberRole,
    MerchantNotification,
    MerchantOrderVerification,
    MerchantProfile,
    MerchantStore,
    MerchantStoreMembership,
    MerchantStorePermission,
    Notification,
    NotificationType,
    Order,
    OrderAppointmentLog,
    OrderItem,
    OrderNote,
    OrderStatus,
    PaymentStatus,
    PointsRecord,
    PointsType,
    ProductStore,
    ServiceItem,
    UnifiedOrder,
    UnifiedOrderStatus,
    User,
)
from app.schemas.merchant import (
    AppointmentTimeAdjustRequest,
    CalendarDaySummary,
    CalendarMonthlyResponse,
    DailyAppointmentItem,
    DailyAppointmentResponse,
    MerchantDashboardResponse,
    MerchantNotificationResponse,
    MerchantProfileResponse,
    MerchantVerifyOrderResponse,
    MerchantVerifyRequest,
    MerchantVerificationRecordResponse,
    MerchantStoreResponse,
    OrderConfirmResponse,
    OrderNoteCreate,
    OrderNoteResponse,
)

router = APIRouter(prefix="/api/merchant", tags=["商家端"])

merchant_dep = require_identity("merchant_owner", "merchant_staff")
FULL_MODULE_CODES = ["dashboard", "verify", "records", "messages", "profile"]


def _safe_user_name(user: User) -> str:
    return user.nickname or user.phone or f"用户{user.id}"


async def _get_store_permissions(
    db: AsyncSession,
    membership_id: int,
    member_role: MerchantMemberRole,
) -> list[str]:
    if member_role == MerchantMemberRole.owner:
        return FULL_MODULE_CODES
    result = await db.execute(
        select(MerchantStorePermission.module_code).where(
            MerchantStorePermission.membership_id == membership_id
        )
    )
    return sorted(set(result.scalars().all()))


async def _ensure_store_access(
    db: AsyncSession,
    user_id: int,
    store_id: int,
    module_code: Optional[str] = None,
):
    result = await db.execute(
        select(MerchantStoreMembership, MerchantStore)
        .join(MerchantStore, MerchantStore.id == MerchantStoreMembership.store_id)
        .where(
            MerchantStoreMembership.user_id == user_id,
            MerchantStoreMembership.store_id == store_id,
            MerchantStoreMembership.status == "active",
            MerchantStore.status == "active",
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=403, detail="当前门店无权限")
    membership, store = row
    module_codes = await _get_store_permissions(db, membership.id, membership.member_role)
    if module_code and module_code not in module_codes:
        raise HTTPException(status_code=403, detail="当前门店模块无权限")
    return membership, store, module_codes


@router.get("/stores")
async def list_accessible_stores(
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MerchantStoreMembership, MerchantStore)
        .join(MerchantStore, MerchantStore.id == MerchantStoreMembership.store_id)
        .where(
            MerchantStoreMembership.user_id == current_user.id,
            MerchantStoreMembership.status == "active",
            MerchantStore.status == "active",
        )
        .order_by(MerchantStore.store_name.asc())
    )
    items = []
    for membership, store in result.all():
        module_codes = await _get_store_permissions(db, membership.id, membership.member_role)
        items.append(
            MerchantStoreResponse(
                id=store.id,
                store_name=store.store_name,
                store_code=store.store_code,
                contact_name=store.contact_name,
                contact_phone=store.contact_phone,
                address=store.address,
                status=store.status,
                member_role=membership.member_role.value,
                module_codes=module_codes,
            )
        )
    return {"items": items}


@router.get("/dashboard", response_model=MerchantDashboardResponse)
async def get_dashboard(
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    _, store, _ = await _ensure_store_access(db, current_user.id, store_id, "dashboard")
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)

    count_result = await db.execute(
        select(func.count(MerchantOrderVerification.id)).where(
            MerchantOrderVerification.store_id == store_id,
            MerchantOrderVerification.verified_at >= today_start,
            MerchantOrderVerification.verified_at < tomorrow,
        )
    )
    today_count = count_result.scalar() or 0

    amount_result = await db.execute(
        select(func.sum(Order.paid_amount))
        .join(MerchantOrderVerification, MerchantOrderVerification.order_id == Order.id)
        .where(
            MerchantOrderVerification.store_id == store_id,
            MerchantOrderVerification.verified_at >= today_start,
            MerchantOrderVerification.verified_at < tomorrow,
        )
    )
    today_amount = float(amount_result.scalar() or 0)

    product_ids_subq = select(ProductStore.product_id).where(ProductStore.store_id == store_id)
    order_ids_subq = (
        select(OrderItem.order_id)
        .where(OrderItem.product_id.in_(product_ids_subq))
        .distinct()
    )

    today_orders_result = await db.execute(
        select(func.count(UnifiedOrder.id)).where(
            UnifiedOrder.id.in_(order_ids_subq),
            UnifiedOrder.created_at >= today_start,
            UnifiedOrder.created_at < tomorrow,
        )
    )
    today_orders = today_orders_result.scalar() or 0

    pending_verify_result = await db.execute(
        select(func.count(UnifiedOrder.id)).where(
            UnifiedOrder.id.in_(order_ids_subq),
            UnifiedOrder.status == UnifiedOrderStatus.pending_use,
        )
    )
    pending_verify = pending_verify_result.scalar() or 0

    recent_orders_result = await db.execute(
        select(UnifiedOrder)
        .where(UnifiedOrder.id.in_(order_ids_subq))
        .order_by(UnifiedOrder.created_at.desc())
        .limit(5)
    )
    recent_orders = []
    for uo in recent_orders_result.scalars().all():
        oi_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == uo.id).limit(1)
        )
        oi = oi_result.scalar_one_or_none()
        recent_orders.append({
            "order_id": uo.id,
            "product_name": oi.product_name if oi else "",
            "amount": float(uo.total_amount or 0),
            "created_at": uo.created_at.isoformat() if uo.created_at else None,
            "status": uo.status.value if hasattr(uo.status, "value") else str(uo.status),
        })

    return MerchantDashboardResponse(
        selected_store_id=store.id,
        selected_store_name=store.store_name,
        today_count=today_count,
        today_amount=today_amount,
        today_orders=today_orders,
        today_verifications=today_count,
        pending_verify=pending_verify,
        recent_orders=recent_orders,
    )


@router.get("/orders/verify-code/{code}", response_model=MerchantVerifyOrderResponse)
async def get_order_by_verify_code(
    code: str,
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id, "verify")

    order_result = await db.execute(select(Order).where(Order.verification_code == code))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="未找到对应订单")

    service_result = await db.execute(select(ServiceItem).where(ServiceItem.id == order.service_item_id))
    service_item = service_result.scalar_one_or_none()
    user_result = await db.execute(select(User).where(User.id == order.user_id))
    order_user = user_result.scalar_one_or_none()

    verify_result = await db.execute(
        select(MerchantOrderVerification).where(MerchantOrderVerification.order_id == order.id)
    )
    verification = verify_result.scalar_one_or_none()

    return MerchantVerifyOrderResponse(
        id=order.id,
        order_no=order.order_no,
        service_name=service_item.name if service_item else "服务订单",
        user_name=_safe_user_name(order_user) if order_user else "用户",
        amount=float(order.paid_amount or order.total_amount or 0),
        create_time=order.created_at,
        status="verified" if verification else "pending",
        verification_code=order.verification_code,
    )


@router.post("/orders/{order_id}/verify")
async def verify_order(
    order_id: int,
    data: MerchantVerifyRequest,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    _, store, _ = await _ensure_store_access(db, current_user.id, data.store_id, "verify")

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.verification_code != data.code:
        raise HTTPException(status_code=400, detail="验证码不正确")

    existing_result = await db.execute(
        select(MerchantOrderVerification).where(MerchantOrderVerification.order_id == order.id)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该订单已核销")

    order.order_status = OrderStatus.completed
    order.payment_status = PaymentStatus.paid
    order.verified_at = datetime.utcnow()
    order.verified_by = current_user.id
    order.updated_at = datetime.utcnow()

    db.add(
        MerchantOrderVerification(
            order_id=order.id,
            store_id=store.id,
            verified_by_user_id=current_user.id,
            verified_at=datetime.utcnow(),
        )
    )

    db.add(
        PointsRecord(
            user_id=order.user_id,
            points=int(float(order.total_amount or 0)),
            type=PointsType.purchase,
            description=f"消费积分 {order.order_no}",
            order_id=order.id,
        )
    )
    user_result = await db.execute(select(User).where(User.id == order.user_id))
    order_user = user_result.scalar_one_or_none()
    if order_user:
        order_user.points += int(float(order.total_amount or 0))
        db.add(
            Notification(
                user_id=order.user_id,
                title="订单已核销",
                content=f"您的订单 {order.order_no} 已在 {store.store_name} 核销完成。",
                type=NotificationType.order,
            )
        )

    db.add(
        MerchantNotification(
            user_id=current_user.id,
            store_id=store.id,
            title="核销成功",
            content=f"订单 {order.order_no} 已核销完成。",
        )
    )
    return {"message": "订单核销成功"}


@router.get("/orders/records")
async def list_verification_records(
    store_id: int = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id, "records")

    filters = [MerchantOrderVerification.store_id == store_id]
    if start_date:
        filters.append(MerchantOrderVerification.verified_at >= datetime.fromisoformat(f"{start_date}T00:00:00"))
    if end_date:
        filters.append(MerchantOrderVerification.verified_at <= datetime.fromisoformat(f"{end_date}T23:59:59"))

    total_result = await db.execute(
        select(func.count(MerchantOrderVerification.id)).where(and_(*filters))
    )
    total = total_result.scalar() or 0

    records_result = await db.execute(
        select(MerchantOrderVerification)
        .where(and_(*filters))
        .order_by(MerchantOrderVerification.verified_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = []
    for verification in records_result.scalars().all():
        order_result = await db.execute(select(Order).where(Order.id == verification.order_id))
        order = order_result.scalar_one_or_none()
        if not order:
            continue
        service_result = await db.execute(select(ServiceItem).where(ServiceItem.id == order.service_item_id))
        service_item = service_result.scalar_one_or_none()
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        order_user = user_result.scalar_one_or_none()
        store_result = await db.execute(select(MerchantStore).where(MerchantStore.id == verification.store_id))
        store = store_result.scalar_one_or_none()
        items.append(
            MerchantVerificationRecordResponse(
                id=verification.id,
                order_no=order.order_no,
                service_name=service_item.name if service_item else "服务订单",
                user_name=_safe_user_name(order_user) if order_user else "用户",
                amount=float(order.paid_amount or order.total_amount or 0),
                verify_time=verification.verified_at,
                store_id=verification.store_id,
                store_name=store.store_name if store else "",
            )
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/notifications")
async def list_merchant_notifications(
    store_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    filters = [MerchantNotification.user_id == current_user.id]
    if store_id is not None:
        await _ensure_store_access(db, current_user.id, store_id, "messages")
        filters.append(or_(MerchantNotification.store_id == store_id, MerchantNotification.store_id.is_(None)))

    total_result = await db.execute(
        select(func.count(MerchantNotification.id)).where(and_(*filters))
    )
    total = total_result.scalar() or 0

    unread_result = await db.execute(
        select(func.count(MerchantNotification.id)).where(
            and_(*filters),
            MerchantNotification.is_read == False,
        )
    )
    unread_count = unread_result.scalar() or 0

    result = await db.execute(
        select(MerchantNotification)
        .where(and_(*filters))
        .order_by(MerchantNotification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [MerchantNotificationResponse.model_validate(item) for item in result.scalars().all()]
    return {"items": items, "total": total, "unread_count": unread_count, "page": page, "page_size": page_size}


@router.put("/notifications/{notification_id}/read")
async def mark_merchant_notification_read(
    notification_id: int,
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MerchantNotification).where(
            MerchantNotification.id == notification_id,
            MerchantNotification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="消息不存在")
    notification.is_read = True
    return {"message": "已标记为已读"}


# [2026-04-26 PRD v1.0 §B1 修复]
# 老 GET /api/merchant/profile 接口（仅返回 nickname/avatar）已删除。
# 与 backend/app/api/account_security.py:merchant_get_profile 路径完全相同时，
# FastAPI 会按注册顺序覆盖，导致前端拿不到完整 8 字段（root cause）。
# 现在唯一实现保留在 account_security.py 中，返回完整字段。


@router.put("/notifications/read-all")
async def mark_all_merchant_notifications_read(
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(MerchantNotification)
        .where(
            MerchantNotification.user_id == current_user.id,
            MerchantNotification.is_read == False,
        )
        .values(is_read=True)
    )
    return {"message": "已全部标记为已读"}


# ─────────── 预约日历 ───────────


def _heat_level(count: int) -> str:
    if count == 0:
        return "low"
    if count <= 3:
        return "medium"
    return "high"


@router.get("/calendar/monthly", response_model=CalendarMonthlyResponse)
async def get_monthly_calendar(
    month: str = Query(..., description="YYYY-MM"),
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    try:
        year, mon = map(int, month.split("-"))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="月份格式: YYYY-MM")

    _, days_in_month = monthrange(year, mon)
    month_start = datetime(year, mon, 1)
    month_end = datetime(year, mon, days_in_month, 23, 59, 59)

    product_ids_subq = select(ProductStore.product_id).where(ProductStore.store_id == store_id)
    order_ids_subq = (
        select(OrderItem.order_id)
        .where(OrderItem.product_id.in_(product_ids_subq))
        .distinct()
    )

    result = await db.execute(
        select(OrderItem)
        .where(
            OrderItem.order_id.in_(order_ids_subq),
            OrderItem.appointment_time.isnot(None),
            OrderItem.appointment_time >= month_start,
            OrderItem.appointment_time <= month_end,
        )
    )
    items = result.scalars().all()

    day_map: dict[str, dict] = {}
    for d in range(1, days_in_month + 1):
        ds = f"{year}-{mon:02d}-{d:02d}"
        day_map[ds] = {"count": 0, "morning": 0, "afternoon": 0, "evening": 0}

    for item in items:
        appt = item.appointment_time
        if not appt:
            continue
        ds = appt.strftime("%Y-%m-%d")
        if ds not in day_map:
            continue
        day_map[ds]["count"] += 1
        hour = appt.hour
        if hour < 12:
            day_map[ds]["morning"] += 1
        elif hour < 18:
            day_map[ds]["afternoon"] += 1
        else:
            day_map[ds]["evening"] += 1

    days = []
    for ds, info in sorted(day_map.items()):
        days.append(CalendarDaySummary(
            date=ds,
            count=info["count"],
            morning_count=info["morning"],
            afternoon_count=info["afternoon"],
            evening_count=info["evening"],
            heat_level_morning=_heat_level(info["morning"]),
            heat_level_afternoon=_heat_level(info["afternoon"]),
            heat_level_evening=_heat_level(info["evening"]),
        ))

    return CalendarMonthlyResponse(days=days)


@router.get("/calendar/daily", response_model=DailyAppointmentResponse)
async def get_daily_calendar(
    date_str: str = Query(..., alias="date", description="YYYY-MM-DD"),
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式: YYYY-MM-DD")

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    product_ids_subq = select(ProductStore.product_id).where(ProductStore.store_id == store_id)
    order_ids_subq = (
        select(OrderItem.order_id)
        .where(OrderItem.product_id.in_(product_ids_subq))
        .distinct()
    )

    result = await db.execute(
        select(OrderItem, UnifiedOrder)
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            OrderItem.order_id.in_(order_ids_subq),
            OrderItem.appointment_time.isnot(None),
            OrderItem.appointment_time >= day_start,
            OrderItem.appointment_time < day_end,
        )
        .order_by(OrderItem.appointment_time.asc())
    )

    items = []
    for oi, order in result.all():
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        time_slot = oi.appointment_time.strftime("%H:%M") if oi.appointment_time else None
        status_val = order.status
        if hasattr(status_val, "value"):
            status_val = status_val.value
        items.append(DailyAppointmentItem(
            order_id=order.id,
            order_item_id=oi.id,
            time_slot=time_slot,
            customer_name=_safe_user_name(user) if user else "用户",
            product_name=oi.product_name,
            status=status_val,
        ))

    return DailyAppointmentResponse(date=date_str, items=items)


# ─────────── 订单操作增强 ───────────


@router.post("/orders/{order_id}/confirm", response_model=OrderConfirmResponse)
async def merchant_confirm_order(
    order_id: int,
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    result = await db.execute(
        select(UnifiedOrder)
        .where(UnifiedOrder.id == order_id)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.store_confirmed:
        return OrderConfirmResponse(success=False, message="该订单已被确认")

    order.store_confirmed = True
    order.store_confirmed_at = datetime.utcnow()
    if not order.store_id:
        order.store_id = store_id
    order.updated_at = datetime.utcnow()

    db.add(Notification(
        user_id=order.user_id,
        title="门店已确认接单",
        content=f"您的订单 {order.order_no} 已被门店确认，请按预约时间到店。",
        type=NotificationType.order,
    ))

    await db.flush()
    return OrderConfirmResponse(success=True, message="确认接单成功")


@router.put("/orders/{order_id}/appointment-time")
async def merchant_adjust_appointment_time(
    order_id: int,
    data: AppointmentTimeAdjustRequest,
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    oi_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    order_items = list(oi_result.scalars().all())
    if not order_items:
        raise HTTPException(status_code=404, detail="订单项不存在")

    new_time_str = data.new_date
    if data.new_time_slot:
        new_time_str = f"{data.new_date} {data.new_time_slot}"

    try:
        if data.new_time_slot:
            new_dt = datetime.strptime(new_time_str, "%Y-%m-%d %H:%M")
        else:
            new_dt = datetime.strptime(new_time_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式不正确")

    for oi in order_items:
        old_time = oi.appointment_time.isoformat() if oi.appointment_time else None

        db.add(OrderAppointmentLog(
            order_item_id=oi.id,
            old_appointment_time=old_time,
            new_appointment_time=new_time_str,
            changed_by_user_id=current_user.id,
        ))

        oi.appointment_time = new_dt
        appt_data = oi.appointment_data or {}
        if isinstance(appt_data, dict):
            appt_data["date"] = data.new_date
            if data.new_time_slot:
                appt_data["time_slot"] = data.new_time_slot
            oi.appointment_data = appt_data
        oi.updated_at = datetime.utcnow()

    order_result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if order:
        db.add(Notification(
            user_id=order.user_id,
            title="预约时间已调整",
            content=f"您的订单 {order.order_no} 预约时间已调整为 {new_time_str}",
            type=NotificationType.order,
        ))

    await db.flush()
    return {"message": "预约时间已调整"}


@router.post("/orders/{order_id}/notes")
async def merchant_add_order_note(
    order_id: int,
    data: OrderNoteCreate,
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="订单不存在")

    note = OrderNote(
        order_id=order_id,
        store_id=store_id,
        staff_user_id=current_user.id,
        content=data.content,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)

    return OrderNoteResponse(
        id=note.id,
        content=note.content,
        staff_name=current_user.nickname or current_user.phone or f"用户{current_user.id}",
        created_at=note.created_at,
    )


@router.get("/orders/{order_id}/notes")
async def merchant_list_order_notes(
    order_id: int,
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    result = await db.execute(
        select(OrderNote, User)
        .outerjoin(User, User.id == OrderNote.staff_user_id)
        .where(OrderNote.order_id == order_id, OrderNote.store_id == store_id)
        .order_by(OrderNote.created_at.desc())
    )

    items = []
    for note, user in result.all():
        items.append(OrderNoteResponse(
            id=note.id,
            content=note.content,
            staff_name=_safe_user_name(user) if user else "未知",
            created_at=note.created_at,
        ))

    return {"items": items}


# ──────────── 商家订单列表 & 详情 ────────────


@router.get("/orders")
async def merchant_list_orders(
    store_id: int = Query(...),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    product_ids_subq = select(ProductStore.product_id).where(ProductStore.store_id == store_id)
    base_filters = [
        UnifiedOrder.id.in_(
            select(OrderItem.order_id)
            .where(OrderItem.product_id.in_(product_ids_subq))
            .distinct()
        )
    ]
    if status:
        base_filters.append(UnifiedOrder.status == status)
    if start_date:
        base_filters.append(UnifiedOrder.created_at >= datetime.fromisoformat(f"{start_date}T00:00:00"))
    if end_date:
        base_filters.append(UnifiedOrder.created_at <= datetime.fromisoformat(f"{end_date}T23:59:59"))
    if keyword:
        kw = f"%{keyword}%"
        base_filters.append(
            or_(
                UnifiedOrder.order_no.ilike(kw),
                UnifiedOrder.id.in_(
                    select(OrderItem.order_id).where(OrderItem.product_name.ilike(kw))
                ),
            )
        )

    total_result = await db.execute(
        select(func.count(UnifiedOrder.id)).where(and_(*base_filters))
    )
    total = total_result.scalar() or 0

    orders_result = await db.execute(
        select(UnifiedOrder)
        .where(and_(*base_filters))
        .order_by(UnifiedOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = []
    for uo in orders_result.scalars().all():
        user_result = await db.execute(select(User).where(User.id == uo.user_id))
        user = user_result.scalar_one_or_none()
        oi_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == uo.id).limit(1)
        )
        oi = oi_result.scalar_one_or_none()
        store_result = await db.execute(
            select(MerchantStore).where(MerchantStore.id == store_id)
        )
        store = store_result.scalar_one_or_none()
        items.append({
            "order_id": uo.id,
            "order_no": uo.order_no,
            "user_display": _safe_user_name(user) if user else "用户",
            "product_name": oi.product_name if oi else "",
            "created_at": uo.created_at.isoformat() if uo.created_at else None,
            "appointment_time": oi.appointment_time.isoformat() if oi and oi.appointment_time else None,
            "store_id": store_id,
            "store_name": store.store_name if store else "",
            "status": uo.status.value if hasattr(uo.status, "value") else str(uo.status),
            "amount": float(uo.total_amount or 0),
            "attachment_count": 0,
            "is_appointment": bool(oi and oi.appointment_time),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/orders/{order_id}/detail")
async def merchant_get_order_detail(
    order_id: int,
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_store_access(db, current_user.id, store_id)

    uo_result = await db.execute(select(UnifiedOrder).where(UnifiedOrder.id == order_id))
    uo = uo_result.scalar_one_or_none()
    if not uo:
        raise HTTPException(status_code=404, detail="订单不存在")

    user_result = await db.execute(select(User).where(User.id == uo.user_id))
    user = user_result.scalar_one_or_none()
    oi_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == uo.id).limit(1)
    )
    oi = oi_result.scalar_one_or_none()
    store_result = await db.execute(
        select(MerchantStore).where(MerchantStore.id == store_id)
    )
    store = store_result.scalar_one_or_none()

    return {
        "order_id": uo.id,
        "order_no": uo.order_no,
        "user_display": _safe_user_name(user) if user else "用户",
        "product_name": oi.product_name if oi else "",
        "created_at": uo.created_at.isoformat() if uo.created_at else None,
        "appointment_time": oi.appointment_time.isoformat() if oi and oi.appointment_time else None,
        "store_id": store_id,
        "store_name": store.store_name if store else "",
        "status": uo.status.value if hasattr(uo.status, "value") else str(uo.status),
        "amount": float(uo.total_amount or 0),
        "is_appointment": bool(oi and oi.appointment_time),
        "store_confirmed": getattr(uo, "store_confirmed", False),
        "store_confirmed_at": uo.store_confirmed_at.isoformat() if getattr(uo, "store_confirmed_at", None) else None,
    }
