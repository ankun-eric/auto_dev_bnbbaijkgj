import random
import string
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Coupon,
    Notification,
    NotificationType,
    OrderItem,
    OrderRedemption,
    OrderReview,
    PointsRecord,
    PointsType,
    Product,
    RefundRequest,
    UnifiedOrder,
    UnifiedOrderStatus,
    RefundStatusEnum,
    UnifiedPaymentMethod,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.schemas.unified_orders import (
    OrderItemResponse,
    UnifiedOrderCancelRequest,
    UnifiedOrderCreate,
    UnifiedOrderPayRequest,
    UnifiedOrderRefundRequest,
    UnifiedOrderReviewCreate,
    UnifiedOrderResponse,
)

router = APIRouter(prefix="/api/orders/unified", tags=["统一订单"])


def _build_order_response(order) -> UnifiedOrderResponse:
    resp = UnifiedOrderResponse.model_validate(order)
    s = order.status
    if hasattr(s, "value"):
        s = s.value
    rs = order.refund_status
    if hasattr(rs, "value"):
        rs = rs.value
    if s == "cancelled" and rs == "refund_success":
        resp.status_display = "已取消（已退款）"
    return resp


def _generate_order_no() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.digits, k=6))
    return f"UO{ts}{rand}"


def _generate_verification_code() -> str:
    return "".join(random.choices(string.digits, k=6))


@router.post("")
async def create_unified_order(
    data: UnifiedOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.items:
        raise HTTPException(status_code=400, detail="订单商品不能为空")

    product_ids = [item.product_id for item in data.items]
    result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products_map = {p.id: p for p in result.scalars().all()}

    total_amount = 0.0
    order_items = []

    for item_data in data.items:
        product = products_map.get(item_data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"商品ID {item_data.product_id} 不存在")
        if product.status != "active":
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 暂不可购买")
        if product.stock < item_data.quantity:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 库存不足")

        subtotal = float(product.sale_price) * item_data.quantity
        total_amount += subtotal

        images = product.images
        first_image = None
        if images and isinstance(images, list) and len(images) > 0:
            first_image = images[0]

        verification_code = None
        qr_token = None
        fulfillment_val = product.fulfillment_type
        if hasattr(fulfillment_val, "value"):
            fulfillment_val = fulfillment_val.value
        if fulfillment_val == "in_store":
            verification_code = _generate_verification_code()
            qr_token = uuid.uuid4().hex

        order_items.append({
            "product": product,
            "item_data": item_data,
            "subtotal": subtotal,
            "first_image": first_image,
            "verification_code": verification_code,
            "qr_token": qr_token,
        })

    coupon_discount = 0.0
    if data.coupon_id:
        uc_result = await db.execute(
            select(UserCoupon)
            .where(
                UserCoupon.user_id == current_user.id,
                UserCoupon.coupon_id == data.coupon_id,
                UserCoupon.status == UserCouponStatus.unused,
            )
        )
        user_coupon = uc_result.scalar_one_or_none()
        if not user_coupon:
            raise HTTPException(status_code=400, detail="优惠券不可用")

        coupon_result = await db.execute(select(Coupon).where(Coupon.id == data.coupon_id))
        coupon = coupon_result.scalar_one_or_none()
        if coupon:
            if total_amount >= float(coupon.condition_amount):
                coupon_type = coupon.type
                if hasattr(coupon_type, "value"):
                    coupon_type = coupon_type.value
                if coupon_type == "full_reduction":
                    coupon_discount = float(coupon.discount_value)
                elif coupon_type == "discount":
                    coupon_discount = total_amount * (1 - coupon.discount_rate)
                elif coupon_type == "voucher":
                    coupon_discount = float(coupon.discount_value)
            else:
                raise HTTPException(status_code=400, detail="订单金额不满足优惠券使用条件")

    points_deduction = 0
    points_value = 0.0
    if data.points_deduction > 0:
        if current_user.points < data.points_deduction:
            raise HTTPException(status_code=400, detail="积分不足")
        points_deduction = data.points_deduction
        points_value = points_deduction / 100.0

    paid_amount = max(0, total_amount - coupon_discount - points_value)

    order = UnifiedOrder(
        order_no=_generate_order_no(),
        user_id=current_user.id,
        total_amount=total_amount,
        paid_amount=paid_amount,
        points_deduction=points_deduction,
        payment_method=data.payment_method,
        coupon_id=data.coupon_id,
        coupon_discount=coupon_discount,
        shipping_address_id=data.shipping_address_id,
        notes=data.notes,
    )
    db.add(order)
    await db.flush()

    for oi_data in order_items:
        product = oi_data["product"]
        item_d = oi_data["item_data"]
        fulfillment_val = product.fulfillment_type
        if hasattr(fulfillment_val, "value"):
            fulfillment_val = fulfillment_val.value

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            product_image=oi_data["first_image"],
            product_price=float(product.sale_price),
            quantity=item_d.quantity,
            subtotal=oi_data["subtotal"],
            fulfillment_type=fulfillment_val,
            verification_code=oi_data["verification_code"],
            verification_qrcode_token=oi_data["qr_token"],
            total_redeem_count=product.redeem_count * item_d.quantity,
            appointment_data=item_d.appointment_data,
            appointment_time=item_d.appointment_time,
        )
        db.add(oi)

        product.stock -= item_d.quantity
        product.sales_count += item_d.quantity

    if points_deduction > 0:
        current_user.points -= points_deduction
        pr = PointsRecord(
            user_id=current_user.id,
            points=-points_deduction,
            type=PointsType.deduct,
            description=f"订单抵扣 {order.order_no}",
        )
        db.add(pr)

    if data.coupon_id and coupon_discount > 0:
        uc_result2 = await db.execute(
            select(UserCoupon).where(
                UserCoupon.user_id == current_user.id,
                UserCoupon.coupon_id == data.coupon_id,
                UserCoupon.status == UserCouponStatus.unused,
            )
        )
        uc = uc_result2.scalar_one_or_none()
        if uc:
            uc.status = UserCouponStatus.used
            uc.used_at = datetime.utcnow()
            uc.order_id = order.id

    notification = Notification(
        user_id=current_user.id,
        title="订单创建成功",
        content=f"您的订单 {order.order_no} 已创建，请在{order.payment_timeout_minutes}分钟内完成支付。",
        type=NotificationType.order,
    )
    db.add(notification)

    await db.flush()
    await db.refresh(order)

    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == order.id)
    )
    order = result.scalar_one()
    return _build_order_response(order)


@router.get("")
async def list_unified_orders(
    status: Optional[str] = None,
    refund_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(UnifiedOrder).where(UnifiedOrder.user_id == current_user.id)
    count_query = select(func.count(UnifiedOrder.id)).where(UnifiedOrder.user_id == current_user.id)

    if status and status != "all":
        if status == "refund":
            query = query.where(UnifiedOrder.refund_status != "none")
            count_query = count_query.where(UnifiedOrder.refund_status != "none")
        elif status == "pending_review":
            query = query.where(
                UnifiedOrder.status == UnifiedOrderStatus.completed,
                UnifiedOrder.has_reviewed == False,
            )
            count_query = count_query.where(
                UnifiedOrder.status == UnifiedOrderStatus.completed,
                UnifiedOrder.has_reviewed == False,
            )
        elif status == "pending_receipt_use":
            query = query.where(
                UnifiedOrder.status.in_([
                    UnifiedOrderStatus.pending_receipt,
                    UnifiedOrderStatus.pending_use,
                ])
            )
            count_query = count_query.where(
                UnifiedOrder.status.in_([
                    UnifiedOrderStatus.pending_receipt,
                    UnifiedOrderStatus.pending_use,
                ])
            )
        else:
            query = query.where(UnifiedOrder.status == status)
            count_query = count_query.where(UnifiedOrder.status == status)

    if refund_status:
        if refund_status in ("all_refund", "all"):
            query = query.where(UnifiedOrder.refund_status != "none")
            count_query = count_query.where(UnifiedOrder.refund_status != "none")
        elif "," in refund_status:
            rs_values = [v.strip() for v in refund_status.split(",") if v.strip()]
            if rs_values:
                query = query.where(UnifiedOrder.refund_status.in_(rs_values))
                count_query = count_query.where(UnifiedOrder.refund_status.in_(rs_values))
        else:
            query = query.where(UnifiedOrder.refund_status == refund_status)
            count_query = count_query.where(UnifiedOrder.refund_status == refund_status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.options(selectinload(UnifiedOrder.items))
        .order_by(UnifiedOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_build_order_response(o) for o in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/counts")
async def get_order_counts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = UnifiedOrder.user_id == current_user.id

    all_q = select(func.count(UnifiedOrder.id)).where(base)
    pending_payment_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status == UnifiedOrderStatus.pending_payment
    )
    pending_receipt_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status == UnifiedOrderStatus.pending_receipt
    )
    pending_use_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status == UnifiedOrderStatus.pending_use
    )
    completed_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status == UnifiedOrderStatus.completed
    )
    pending_review_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status == UnifiedOrderStatus.completed, UnifiedOrder.has_reviewed == False
    )
    cancelled_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status == UnifiedOrderStatus.cancelled
    )
    refund_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.refund_status != "none"
    )

    total = (await db.execute(all_q)).scalar() or 0
    pp = (await db.execute(pending_payment_q)).scalar() or 0
    pr = (await db.execute(pending_receipt_q)).scalar() or 0
    pu = (await db.execute(pending_use_q)).scalar() or 0
    cp = (await db.execute(completed_q)).scalar() or 0
    prv = (await db.execute(pending_review_q)).scalar() or 0
    cc = (await db.execute(cancelled_q)).scalar() or 0
    rf = (await db.execute(refund_q)).scalar() or 0

    return {
        "all": total,
        "pending_payment": pp,
        "pending_receipt": pr,
        "pending_use": pu,
        "completed": cp,
        "pending_review": prv,
        "cancelled": cc,
        "refund": rf,
    }


@router.get("/{order_id}")
async def get_unified_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return _build_order_response(order)


@router.post("/{order_id}/pay")
async def pay_unified_order(
    order_id: int,
    data: UnifiedOrderPayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "pending_payment":
        raise HTTPException(status_code=400, detail="该订单无法支付")

    order.payment_method = data.payment_method
    order.paid_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    has_delivery = False
    has_in_store = False
    for item in order.items:
        ft = item.fulfillment_type
        if hasattr(ft, "value"):
            ft = ft.value
        if ft == "delivery":
            has_delivery = True
        else:
            has_in_store = True

    if has_delivery and not has_in_store:
        order.status = UnifiedOrderStatus.pending_shipment
    elif has_in_store and not has_delivery:
        order.status = UnifiedOrderStatus.pending_use
    else:
        order.status = UnifiedOrderStatus.pending_use

    return {"message": "支付成功", "order_no": order.order_no}


@router.post("/{order_id}/confirm")
async def confirm_receipt(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val not in ("pending_receipt", "pending_shipment"):
        raise HTTPException(status_code=400, detail="该订单无法确认收货")

    order.status = UnifiedOrderStatus.completed
    order.received_at = datetime.utcnow()
    order.completed_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    pr = PointsRecord(
        user_id=current_user.id,
        points=int(float(order.total_amount)),
        type=PointsType.purchase,
        description=f"消费积分 {order.order_no}",
    )
    db.add(pr)
    current_user.points += int(float(order.total_amount))

    return {"message": "确认收货成功"}


@router.post("/{order_id}/cancel")
async def cancel_unified_order(
    order_id: int,
    data: UnifiedOrderCancelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val not in ("pending_payment",):
        raise HTTPException(status_code=400, detail="该订单无法取消")

    order.status = UnifiedOrderStatus.cancelled
    order.cancelled_at = datetime.utcnow()
    order.cancel_reason = data.cancel_reason
    order.updated_at = datetime.utcnow()

    if order.points_deduction > 0:
        current_user.points += order.points_deduction
        pr = PointsRecord(
            user_id=current_user.id,
            points=order.points_deduction,
            type=PointsType.redeem,
            description=f"订单取消退还积分 {order.order_no}",
        )
        db.add(pr)

    for item in order.items:
        p_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = p_result.scalar_one_or_none()
        if product:
            product.stock += item.quantity
            product.sales_count = max(0, product.sales_count - item.quantity)

    if order.coupon_id:
        uc_result = await db.execute(
            select(UserCoupon).where(
                UserCoupon.user_id == current_user.id,
                UserCoupon.coupon_id == order.coupon_id,
                UserCoupon.order_id == order.id,
            )
        )
        uc = uc_result.scalar_one_or_none()
        if uc:
            uc.status = UserCouponStatus.unused
            uc.used_at = None
            uc.order_id = None

    return {"message": "订单已取消"}


@router.post("/{order_id}/review")
async def review_unified_order(
    order_id: int,
    data: UnifiedOrderReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "completed":
        raise HTTPException(status_code=400, detail="该订单无法评价")

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

    order.has_reviewed = True
    order.updated_at = datetime.utcnow()

    pr = PointsRecord(
        user_id=current_user.id,
        points=10,
        type=PointsType.task,
        description="订单评价奖励",
    )
    db.add(pr)
    current_user.points += 10

    await db.flush()
    await db.refresh(review)
    return {"message": "评价成功", "review_id": review.id}


@router.post("/{order_id}/refund")
async def request_refund(
    order_id: int,
    data: UnifiedOrderRefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val in ("cancelled",):
        raise HTTPException(status_code=400, detail="已取消的订单无法申请退款")

    refund_amount = data.refund_amount or float(order.paid_amount)

    refund_req = RefundRequest(
        order_id=order.id,
        order_item_id=data.order_item_id,
        user_id=current_user.id,
        reason=data.reason,
        refund_amount=refund_amount,
    )
    db.add(refund_req)

    order.refund_status = RefundStatusEnum.applied
    order.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(refund_req)
    return {"message": "退款申请已提交", "refund_id": refund_req.id}
