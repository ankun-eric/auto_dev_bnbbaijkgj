from datetime import datetime, timedelta
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
    OrderStatus,
    PaymentStatus,
    PointsRecord,
    PointsType,
    ServiceItem,
    User,
)
from app.schemas.merchant import (
    MerchantDashboardResponse,
    MerchantNotificationResponse,
    MerchantProfileResponse,
    MerchantVerifyOrderResponse,
    MerchantVerifyRequest,
    MerchantVerificationRecordResponse,
    MerchantStoreResponse,
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

    return MerchantDashboardResponse(
        selected_store_id=store.id,
        selected_store_name=store.store_name,
        today_count=today_count,
        today_amount=today_amount,
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
