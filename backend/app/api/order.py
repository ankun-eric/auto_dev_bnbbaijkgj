import random
import string
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.utils.client_source import require_mobile_verify_client
from app.models.models import (
    Notification,
    NotificationType,
    Order,
    OrderReview,
    OrderStatus,
    PaymentStatus,
    PointsRecord,
    PointsType,
    ServiceItem,
    User,
)
from app.schemas.order import OrderCreate, OrderResponse, OrderReviewCreate, OrderReviewResponse, RefundRequest

router = APIRouter(prefix="/api/orders", tags=["订单"])


def _generate_order_no() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.digits, k=6))
    return f"ORD{ts}{rand}"


@router.post("", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceItem).where(ServiceItem.id == data.service_item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="服务项目不存在")
    if item.status != "active":
        raise HTTPException(status_code=400, detail="该服务项目暂不可用")
    if item.stock < data.quantity:
        raise HTTPException(status_code=400, detail="库存不足")

    total_amount = float(item.price) * data.quantity

    points_deduction = 0
    if data.points_deduction > 0:
        if current_user.points < data.points_deduction:
            raise HTTPException(status_code=400, detail="积分不足")
        points_deduction = min(data.points_deduction, int(total_amount * 100))

    paid_amount = total_amount - (points_deduction / 100)

    verification_code = "".join(random.choices(string.digits, k=6))

    order = Order(
        order_no=_generate_order_no(),
        user_id=current_user.id,
        service_item_id=data.service_item_id,
        quantity=data.quantity,
        total_amount=total_amount,
        paid_amount=max(0, paid_amount),
        points_deduction=points_deduction,
        payment_method=data.payment_method,
        address=data.address,
        notes=data.notes,
        verification_code=verification_code,
    )
    db.add(order)

    item.stock -= data.quantity
    item.sales_count += data.quantity

    if points_deduction > 0:
        current_user.points -= points_deduction
        pr = PointsRecord(
            user_id=current_user.id,
            points=-points_deduction,
            type=PointsType.deduct,
            description=f"订单抵扣 {order.order_no}",
        )
        db.add(pr)

    await db.flush()
    await db.refresh(order)

    notification = Notification(
        user_id=current_user.id,
        title="订单创建成功",
        content=f"您的订单 {order.order_no} 已创建，请尽快完成支付。",
        type=NotificationType.order,
    )
    db.add(notification)

    return OrderResponse.model_validate(order)


@router.get("")
async def list_orders(
    order_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).where(Order.user_id == current_user.id)
    count_query = select(func.count(Order.id)).where(Order.user_id == current_user.id)

    if order_status:
        query = query.where(Order.order_status == order_status)
        count_query = count_query.where(Order.order_status == order_status)
    if payment_status:
        query = query.where(Order.payment_status == payment_status)
        count_query = count_query.where(Order.payment_status == payment_status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [OrderResponse.model_validate(o) for o in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return OrderResponse.model_validate(order)


@router.put("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    cancel_check = order.order_status
    if hasattr(cancel_check, "value"):
        cancel_check = cancel_check.value
    if cancel_check in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="该订单无法取消")

    order.order_status = OrderStatus.cancelled
    order.updated_at = datetime.utcnow()

    if order.points_deduction > 0:
        current_user.points += order.points_deduction
        pr = PointsRecord(
            user_id=current_user.id,
            points=order.points_deduction,
            type=PointsType.redeem,
            description=f"订单取消退还积分 {order.order_no}",
            order_id=order.id,
        )
        db.add(pr)

    item_result = await db.execute(select(ServiceItem).where(ServiceItem.id == order.service_item_id))
    item = item_result.scalar_one_or_none()
    if item:
        item.stock += order.quantity
        item.sales_count = max(0, item.sales_count - order.quantity)

    return {"message": "订单已取消"}


@router.post("/{order_id}/review", response_model=OrderReviewResponse)
async def create_review(
    order_id: int,
    data: OrderReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.order_status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "completed":
        raise HTTPException(status_code=400, detail="只能评价已完成的订单")

    existing = await db.execute(select(OrderReview).where(OrderReview.order_id == order_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该订单已评价")

    review = OrderReview(
        order_id=order_id,
        user_id=current_user.id,
        rating=data.rating,
        content=data.content,
        images=data.images,
    )
    db.add(review)

    pr = PointsRecord(
        user_id=current_user.id,
        points=10,
        type=PointsType.task,
        description="订单评价奖励",
        order_id=order_id,
    )
    db.add(pr)
    current_user.points += 10

    await db.flush()
    await db.refresh(review)
    return OrderReviewResponse.model_validate(review)


@router.post("/{order_id}/verify")
async def verify_order(
    order_id: int,
    request: Request,
    code: str = Query(...),
    current_user: User = Depends(get_current_user),
    _client_type: str = Depends(require_mobile_verify_client),
    db: AsyncSession = Depends(get_db),
):
    # [PRD-05 R-05-04] 即便此旧接口已在 main.py 中注释禁用，依然加上来源校验作为防线。
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.verification_code != code:
        raise HTTPException(status_code=400, detail="验证码不正确")

    order.order_status = OrderStatus.completed
    order.payment_status = PaymentStatus.paid
    order.verified_at = datetime.utcnow()
    order.verified_by = current_user.id
    order.updated_at = datetime.utcnow()

    pr = PointsRecord(
        user_id=order.user_id,
        points=int(float(order.total_amount)),
        type=PointsType.purchase,
        description=f"消费积分 {order.order_no}",
        order_id=order.id,
    )
    db.add(pr)

    user_result = await db.execute(select(User).where(User.id == order.user_id))
    order_user = user_result.scalar_one_or_none()
    if order_user:
        order_user.points += int(float(order.total_amount))

    return {"message": "订单核销成功"}


@router.get("/verify-code/{code}")
async def get_order_by_verify_code(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order).where(Order.verification_code == code)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="未找到对应订单")
    return OrderResponse.model_validate(order)
