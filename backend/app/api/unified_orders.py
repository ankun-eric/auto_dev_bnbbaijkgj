import logging
import random
import string
import uuid
from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Coupon,
    MerchantNotification,
    MerchantStore,
    Notification,
    NotificationType,
    OrderItem,
    OrderRedemption,
    OrderReview,
    PointsRecord,
    PointsType,
    Product,
    ProductStore,
    RefundRequest,
    RefundRequestStatus,
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
    UnifiedOrderRefundCancelRequest,
    UnifiedOrderReviewCreate,
    UnifiedOrderResponse,
    UnifiedOrderSetAppointmentRequest,
)


# PRD「我的订单与售后状态体系优化」: 评价时效（订单完成后 15 天）
REVIEW_VALID_DAYS = 15

router = APIRouter(prefix="/api/orders/unified", tags=["统一订单"])


_STATUS_DISPLAY_MAP = {
    "pending_payment": "待付款",
    "pending_shipment": "待发货",
    "pending_receipt": "待收货",
    "pending_appointment": "待预约",
    "appointed": "已预约",
    "pending_use": "待核销",
    "partial_used": "部分核销",
    "pending_review": "待评价",
    "completed": "已完成",
    "expired": "已过期",
    "refunding": "退款中",
    "refunded": "已退款",
    "cancelled": "已取消",
}

_STATUS_COLOR_MAP = {
    "pending_payment": "#fa8c16",
    "pending_shipment": "#1890ff",
    "pending_receipt": "#13c2c2",
    "pending_appointment": "#722ed1",
    "appointed": "#722ed1",
    "pending_use": "#13c2c2",
    "partial_used": "#faad14",
    "pending_review": "#eb2f96",
    "completed": "#52c41a",
    "expired": "#8c8c8c",
    "refunding": "#f5222d",
    "refunded": "#8c8c8c",
    "cancelled": "#8c8c8c",
}


def _normalize_status(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _earliest_appt_for_order(order):
    """取订单中最早的 appointment_time（用于状态文案与提醒）。"""
    items = getattr(order, "items", None) or []
    times = [it.appointment_time for it in items if getattr(it, "appointment_time", None)]
    return min(times) if times else None


def _display_status_for(order) -> tuple[str, str]:
    """V2: 返回 (display_status_text, color)。
    "已完成" Tab 中包含 expired，但卡片状态文字仍区分。
    "待评价" = completed AND has_reviewed=False（动态计算）。

    [PRD 订单状态机简化方案 v1.0]：
    pending_use / appointed（兼容老订单）显示「待核销（预约 X月X日）」。
    """
    s = _normalize_status(order.status)
    rs = _normalize_status(order.refund_status)
    if s == "cancelled" and rs == "refund_success":
        return "已取消（已退款）", _STATUS_COLOR_MAP["cancelled"]
    if s == "completed" and not bool(getattr(order, "has_reviewed", False)):
        return "待评价", _STATUS_COLOR_MAP["pending_review"]
    if s in ("pending_use", "appointed"):
        appt = _earliest_appt_for_order(order)
        if appt is not None:
            return f"待核销（预约 {appt.month}月{appt.day}日）", _STATUS_COLOR_MAP["pending_use"]
        return "待核销", _STATUS_COLOR_MAP["pending_use"]
    return _STATUS_DISPLAY_MAP.get(s, s), _STATUS_COLOR_MAP.get(s, "#8c8c8c")


def _action_buttons_for(order) -> list[str]:
    """根据当前状态返回可显示的操作按钮 key 列表（前端按 key 渲染）。

    [PRD 订单状态机简化方案 v1.0]：
    - pending_use 阶段必须保留「修改预约 + 取消预约/退款」按钮全程可见
    - appointed 兼容老订单，与 pending_use 同等处理（合并 Tab 后视为同一态）
    """
    s = _normalize_status(order.status)
    rs = _normalize_status(order.refund_status)
    btns: list[str] = []
    if s == "pending_payment":
        btns += ["cancel", "pay"]
    elif s == "pending_receipt":
        btns += ["confirm_receipt"]
    elif s == "pending_appointment":
        btns += ["set_appointment"]
    elif s in ("appointed", "pending_use", "partial_used"):
        # 出码 + 修改预约 + 退款（部分核销不允许改约）
        btns += ["show_qrcode"]
        if s != "partial_used" and rs in ("none", "rejected", ""):
            btns += ["modify_appointment"]
        if rs in ("none", "rejected", ""):
            btns += ["apply_refund"]
        elif rs in ("applied",):
            btns += ["withdraw_refund"]
    elif s == "completed":
        if not bool(getattr(order, "has_reviewed", False)):
            btns += ["review"]
        btns += ["rebuy"]
    elif s == "expired":
        btns += ["rebuy"]
    elif s in ("refunding",):
        btns += ["view_refund"]
    return btns


# PRD「我的订单与售后状态体系优化」F-05/F-07：4 个统一逻辑状态
# 待审核 / 处理中 / 已完成 / 已驳回（适用 H5 退款列表 + 全部订单退货售后 + 后台筛选）
_AFTERSALES_LABEL = {
    "pending": "待审核",
    "processing": "处理中",
    "completed": "已完成",
    "rejected": "已驳回",
    "none": "无",
}


def _aftersales_logical_status(order) -> str:
    """根据当前订单的 status + refund_status 计算逻辑售后状态：
    - none      : 未发起售后（refund_status == 'none' 且 status 非 refunding/refunded）
    - pending   : 待审核（refund_status in {applied, reviewing}）
    - processing: 处理中（status == refunding 或 refund_status in {approved, returning}）
    - completed : 已完成（status == refunded 或 refund_status == refund_success）
    - rejected  : 已驳回（refund_status == rejected）
    取「最近一次状态归档」语义。
    """
    s = _normalize_status(order.status)
    rs = _normalize_status(order.refund_status)
    if rs == "rejected":
        return "rejected"
    if s == "refunded" or rs == "refund_success":
        return "completed"
    # 待审核优先级高于"处理中"——用户刚申请时 status 已被业务设为 refunding，
    # 但 refund_status 仍为 applied/reviewing，此时应展示"待审核"
    if rs in ("applied", "reviewing"):
        return "pending"
    if s == "refunding" or rs in ("approved", "returning"):
        return "processing"
    return "none"


def _build_order_response(order) -> UnifiedOrderResponse:
    resp = UnifiedOrderResponse.model_validate(order)
    s = _normalize_status(order.status)
    rs = _normalize_status(order.refund_status)
    if s == "cancelled" and rs == "refund_success":
        resp.status_display = "已取消（已退款）"
    # PRD V2：在响应中追加 display_status / display_status_color / action_buttons / badges
    text, color = _display_status_for(order)
    resp.display_status = text
    resp.display_status_color = color
    resp.action_buttons = _action_buttons_for(order)
    badges: list[str] = []
    if s in ("pending_use", "partial_used"):
        badges.append("可核销")
    if s == "partial_used":
        badges.append("部分已核销")
    if s == "appointed":
        badges.append("已预约")
    resp.badges = badges
    resp.store_name = order.store.store_name if order.store else None

    # PRD「我的订单与售后状态体系优化」: 售后逻辑状态 + 15 天评价时效 + 撤销可见性
    logical = _aftersales_logical_status(order)
    resp.aftersales_logical_status = logical
    resp.aftersales_logical_label = _AFTERSALES_LABEL.get(logical, "无")
    # F-13：仅当售后处于「待审核」时，用户可撤销
    resp.can_withdraw_refund = (logical == "pending")

    # F-12：评价时效 = completed_at + 15 天
    completed_at = getattr(order, "completed_at", None)
    if s == "completed" and completed_at is not None:
        deadline = completed_at + timedelta(days=REVIEW_VALID_DAYS)
        resp.review_deadline_at = deadline
        resp.review_expired = (
            datetime.utcnow() > deadline and not bool(getattr(order, "has_reviewed", False))
        )
        # 重新计算 action_buttons：超期未评价时去掉 review、添加 review_expired
        if not bool(getattr(order, "has_reviewed", False)):
            if resp.review_expired:
                resp.action_buttons = [
                    b for b in resp.action_buttons if b != "review"
                ] + ["review_expired"]
        else:
            # 已评价：把 review 替换为 view_review
            resp.action_buttons = [
                ("view_review" if b == "review" else b)
                for b in resp.action_buttons if b != "review"
            ]
            if "view_review" not in resp.action_buttons:
                resp.action_buttons.append("view_review")
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

    # 预加载所有涉及的 SKU
    sku_ids = [item.sku_id for item in data.items if getattr(item, "sku_id", None)]
    skus_map: dict[int, "ProductSku"] = {}
    if sku_ids:
        from app.models.models import ProductSku as _SKU
        sku_result = await db.execute(select(_SKU).where(_SKU.id.in_(sku_ids)))
        skus_map = {s.id: s for s in sku_result.scalars().all()}

    total_amount = 0.0
    order_items = []

    for item_data in data.items:
        product = products_map.get(item_data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"商品ID {item_data.product_id} 不存在")
        if product.status != "active":
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 暂不可购买")

        # 多规格商品：必须传 sku_id 且 sku 必须属于该商品、状态启用、库存足
        sku = None
        item_price = float(product.sale_price)
        if int(product.spec_mode or 1) == 2:
            if not item_data.sku_id:
                raise HTTPException(status_code=400, detail=f"商品 {product.name} 必须选择规格")
            sku = skus_map.get(item_data.sku_id)
            if not sku or sku.product_id != product.id:
                raise HTTPException(status_code=400, detail="所选规格不存在")
            if int(sku.status or 1) != 1:
                raise HTTPException(status_code=400, detail=f"规格 {sku.spec_name} 已停用")
            if (sku.stock or 0) < item_data.quantity:
                raise HTTPException(status_code=400, detail=f"规格 {sku.spec_name} 库存不足")
            item_price = float(sku.sale_price)
        else:
            if (product.stock or 0) < item_data.quantity:
                raise HTTPException(status_code=400, detail=f"商品 {product.name} 库存不足")

        subtotal = item_price * item_data.quantity
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
            "sku": sku,
            "item_price": item_price,
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
            # ── V2.2：扣除「被排除商品」金额，再用净额参与门槛 / 折扣计算（PRD F6）──
            exclude_ids_raw = getattr(coupon, "exclude_ids", None) or []
            excluded_set: set[int] = set()
            if isinstance(exclude_ids_raw, list):
                for x in exclude_ids_raw:
                    try:
                        excluded_set.add(int(x))
                    except (TypeError, ValueError):
                        continue
            elif isinstance(exclude_ids_raw, str):
                for x in exclude_ids_raw.split(","):
                    try:
                        excluded_set.add(int(x.strip()))
                    except (TypeError, ValueError):
                        continue

            eligible_amount = total_amount
            if excluded_set:
                excluded_amount = sum(
                    oi["subtotal"] for oi in order_items if oi["product"].id in excluded_set
                )
                eligible_amount = max(0.0, total_amount - excluded_amount)

            if eligible_amount >= float(coupon.condition_amount):
                coupon_type = coupon.type
                if hasattr(coupon_type, "value"):
                    coupon_type = coupon_type.value
                if coupon_type == "full_reduction":
                    coupon_discount = float(coupon.discount_value)
                elif coupon_type == "discount":
                    coupon_discount = eligible_amount * (1 - coupon.discount_rate)
                elif coupon_type == "voucher":
                    coupon_discount = float(coupon.discount_value)
                # 折扣不超过可享券金额，避免负数
                coupon_discount = min(coupon_discount, eligible_amount)
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

        sku = oi_data.get("sku")
        item_price = oi_data.get("item_price", float(product.sale_price))

        appt_mode = getattr(product, "appointment_mode", "none") or "none"
        if hasattr(appt_mode, "value"):
            appt_mode = appt_mode.value
        purchase_appt_mode = getattr(product, "purchase_appointment_mode", None) or ""
        if hasattr(purchase_appt_mode, "value"):
            purchase_appt_mode = purchase_appt_mode.value
        # [先下单后预约 Bug 修复 v1.0]
        # 当商品配置为「先下单后预约」(appointment_later / appoint_later) 时：
        # 1) 不要求前端必传 appointment_time
        # 2) 即使前端误传了 appointment_time / appointment_data，后端也主动忽略不写入
        # 3) 跳过预约时间的全部校验（日期范围、时段冲突、容量等）
        is_book_after_pay = purchase_appt_mode in ("appointment_later", "appoint_later")
        if is_book_after_pay and appt_mode != "none":
            if getattr(item_d, "appointment_time", None) or getattr(item_d, "appointment_data", None):
                logger.info(
                    "[book_after_pay] 商品 %s 配置为先下单后预约，已忽略前端误传的 appointment_time/appointment_data",
                    product.id,
                )
            item_d.appointment_time = None
            item_d.appointment_data = None
        if appt_mode != "none" and purchase_appt_mode == "purchase_with_appointment":
            if not item_d.appointment_time:
                raise HTTPException(status_code=400, detail="预约类商品必须选择预约时间")
            adv = getattr(product, "advance_days", None)
            if adv and int(adv) > 0:
                # BUG-PRODUCT-APPT-002：可预约范围统一公式
                # include_today=True  → [today, today + N - 1]
                # include_today=False → [today + 1, today + N]
                inc_today = getattr(product, "include_today", True)
                if inc_today is None:
                    inc_today = True
                if inc_today:
                    start_date = date.today()
                    end_date = start_date + timedelta(days=int(adv) - 1)
                else:
                    start_date = date.today() + timedelta(days=1)
                    end_date = start_date + timedelta(days=int(adv) - 1)
                today_start = datetime.combine(start_date, datetime.min.time())
                today_end = datetime.combine(end_date, datetime.max.time())
                appt_time = item_d.appointment_time
                if isinstance(appt_time, str):
                    appt_time = datetime.fromisoformat(appt_time)
                if appt_time < today_start or appt_time > today_end:
                    raise HTTPException(status_code=400, detail="预约日期超出可预约范围")

            # Bug1 兜底：已过时段校验
            appt_data = item_d.appointment_data or {}
            selected_slot = appt_data.get("time_slot", "") if isinstance(appt_data, dict) else ""
            selected_date_str = appt_data.get("date", "") if isinstance(appt_data, dict) else ""
            if selected_slot and selected_date_str:
                try:
                    selected_date_obj = date.fromisoformat(selected_date_str)
                except (ValueError, TypeError):
                    selected_date_obj = None
                if selected_date_obj == date.today():
                    slot_end = selected_slot.split("-")[-1] if "-" in selected_slot else ""
                    if slot_end:
                        try:
                            now_time = datetime.now().time()
                            end_parts = slot_end.split(":")
                            from datetime import time as dt_time
                            end_time_obj = dt_time(int(end_parts[0]), int(end_parts[1]))
                            if end_time_obj <= now_time:
                                raise HTTPException(status_code=400, detail="该时段已过，请选择其他时段")
                        except (ValueError, IndexError):
                            pass

            # [2026-05-02 H5 下单流程优化 PRD v1.0]
            # 容量校验改为「门店 slot_capacity」粒度（默认 10），口径 = 已支付 + 待支付 15 分钟内。
            # appointment_data.store_id 优先，缺省时回退商品绑定的第一个门店；
            # 商品 time_slots[].capacity 字段保留但下单不再读取（PRD §2.1）。
            target_store_id = None
            if isinstance(appt_data, dict):
                try:
                    sid_raw = appt_data.get("store_id")
                    if sid_raw is not None and sid_raw != "":
                        target_store_id = int(sid_raw)
                except (TypeError, ValueError):
                    target_store_id = None
            if target_store_id is None:
                ps_res = await db.execute(
                    select(ProductStore.store_id)
                    .where(ProductStore.product_id == product.id)
                    .order_by(ProductStore.store_id.asc())
                    .limit(1)
                )
                first_sid = ps_res.scalar_one_or_none()
                if first_sid is not None:
                    target_store_id = int(first_sid)

            if selected_slot and selected_date_str and target_store_id:
                try:
                    q_date = date.fromisoformat(selected_date_str)
                except (ValueError, TypeError):
                    q_date = None
                if q_date:
                    store_res = await db.execute(
                        select(MerchantStore).where(MerchantStore.id == target_store_id)
                    )
                    target_store = store_res.scalar_one_or_none()
                    capacity = int(getattr(target_store, "slot_capacity", 10) or 10) if target_store else 10
                    biz_start = getattr(target_store, "business_start", None) if target_store else None
                    biz_end = getattr(target_store, "business_end", None) if target_store else None

                    # 商品时段必须落在门店营业时段之内
                    if biz_start and biz_end:
                        try:
                            slot_start, slot_end = selected_slot.split("-")
                            if slot_start < biz_start or slot_end > biz_end:
                                raise HTTPException(
                                    status_code=400,
                                    detail="所选时段不在该门店营业时段内，请重新选择",
                                )
                        except ValueError:
                            pass

                    # 占用数 = 已支付 + 待支付（15 分钟内未取消）
                    # 已支付 = 非 pending_payment 且 非 cancelled（含 pending_shipment/pending_receipt/pending_use/pending_review/completed）
                    fifteen_min_ago = datetime.utcnow() - timedelta(minutes=15)
                    paid_like = [
                        UnifiedOrderStatus.pending_shipment,
                        UnifiedOrderStatus.pending_receipt,
                        UnifiedOrderStatus.pending_use,
                        UnifiedOrderStatus.pending_review,
                        UnifiedOrderStatus.completed,
                    ]
                    booked_q = await db.execute(
                        select(func.count(OrderItem.id))
                        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
                        .where(
                            OrderItem.product_id == product.id,
                            func.date(OrderItem.appointment_time) == q_date,
                            func.json_extract(OrderItem.appointment_data, "$.time_slot") == selected_slot,
                            UnifiedOrder.store_id == target_store_id,
                            (
                                (UnifiedOrder.status.in_(paid_like))
                                | (
                                    (UnifiedOrder.status == UnifiedOrderStatus.pending_payment)
                                    & (UnifiedOrder.created_at >= fifteen_min_ago)
                                )
                            ),
                        )
                    )
                    booked_count = booked_q.scalar() or 0
                    if booked_count >= capacity:
                        raise HTTPException(
                            status_code=400,
                            detail="该时段名额已满，请选择其他时段",
                        )

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            sku_id=sku.id if sku else None,
            sku_name=sku.spec_name if sku else None,
            product_name=product.name,
            product_image=oi_data["first_image"],
            product_price=item_price,
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

        if sku is not None:
            sku.stock = max(0, (sku.stock or 0) - item_d.quantity)
        else:
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

    # [2026-05-02 H5 下单流程优化 PRD v1.0]
    # 优先使用 appointment_data.store_id 作为订单 store_id；缺失时回退商品绑定的第一个门店。
    user_chosen_store_id: Optional[int] = None
    for item in data.items:
        appt = getattr(item, "appointment_data", None) or {}
        if isinstance(appt, dict):
            sid_raw = appt.get("store_id")
            try:
                if sid_raw is not None and sid_raw != "":
                    user_chosen_store_id = int(sid_raw)
                    break
            except (TypeError, ValueError):
                continue

    if user_chosen_store_id is not None:
        order.store_id = user_chosen_store_id
    else:
        all_product_ids = list({item.product_id for item in data.items})
        store_result = await db.execute(
            select(ProductStore.store_id)
            .where(ProductStore.product_id.in_(all_product_ids))
            .distinct()
        )
        bound_store_ids = [row[0] for row in store_result.all()]
        if bound_store_ids:
            order.store_id = bound_store_ids[0]

    notification = Notification(
        user_id=current_user.id,
        title="订单创建成功",
        content=f"您的订单 {order.order_no} 已创建，请在{order.payment_timeout_minutes}分钟内完成支付。",
        type=NotificationType.order,
    )
    db.add(notification)

    # 通知绑定门店的员工有新订单
    if order.store_id:
        from app.models.models import MerchantStoreMembership
        staff_result = await db.execute(
            select(MerchantStoreMembership.user_id).where(
                MerchantStoreMembership.store_id == order.store_id,
                MerchantStoreMembership.status == "active",
            )
        )
        for (uid,) in staff_result.all():
            db.add(MerchantNotification(
                user_id=uid,
                store_id=order.store_id,
                title="新订单通知",
                content=f"新订单 {order.order_no}，请及时确认接单。",
                notification_type="order",
            ))

    await db.flush()
    await db.refresh(order)

    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items), selectinload(UnifiedOrder.store))
        .where(UnifiedOrder.id == order.id)
    )
    order = result.scalar_one()
    return _build_order_response(order)


def _apply_v2_tab_filter(query, count_query, tab: str, sub_tab: Optional[str] = None):
    """PRD V2 客户端 5 Tab + 全部 + 退货售后子筛选 → SQL where 子句。"""
    # 全部 / pending_payment / pending_receipt / pending_use / completed / refund_aftersales
    if tab in ("all", "", None):
        return query, count_query

    if tab == "pending_payment":
        cond = UnifiedOrder.status == UnifiedOrderStatus.pending_payment
        return query.where(cond), count_query.where(cond)

    if tab == "pending_receipt":
        # V2：映射 pending_shipment + pending_receipt 两个状态（待收货 Tab）
        cond = UnifiedOrder.status.in_([
            UnifiedOrderStatus.pending_shipment,
            UnifiedOrderStatus.pending_receipt,
        ])
        return query.where(cond), count_query.where(cond)

    if tab == "pending_use":
        # V2：待使用 Tab 包含 pending_appointment / appointed / pending_use / partial_used
        cond = UnifiedOrder.status.in_([
            UnifiedOrderStatus.pending_appointment,
            UnifiedOrderStatus.appointed,
            UnifiedOrderStatus.pending_use,
            UnifiedOrderStatus.partial_used,
        ])
        return query.where(cond), count_query.where(cond)

    if tab == "completed":
        # V2：已完成 Tab 包含 completed + expired
        cond = UnifiedOrder.status.in_([
            UnifiedOrderStatus.completed,
            UnifiedOrderStatus.expired,
        ])
        return query.where(cond), count_query.where(cond)

    if tab == "refund_aftersales":
        # PRD「我的订单与售后状态体系优化」F-05/F-07：4 个统一逻辑子筛选
        # 待审核 / 处理中 / 已完成 / 已驳回，与后台、独立退款列表完全一致
        # 同时兼容旧 key（reviewing/refunding/refunded）作为别名映射
        if sub_tab in (None, "", "all"):
            cond = UnifiedOrder.status.in_([
                UnifiedOrderStatus.refunding,
                UnifiedOrderStatus.refunded,
            ]) | (UnifiedOrder.refund_status.in_([
                "applied", "reviewing", "approved", "rejected", "returning", "refund_success"
            ]))
            return query.where(cond), count_query.where(cond)
        # 待审核 = 用户已申请、客服未处理（applied / reviewing）
        if sub_tab in ("pending", "reviewing"):
            cond = UnifiedOrder.refund_status.in_(["applied", "reviewing"])
            return query.where(cond), count_query.where(cond)
        # 处理中 = 客服通过、打款中、退货寄回中（排除"待审核"语义的订单）
        if sub_tab in ("processing", "refunding"):
            # 优先显式语义：refund_status in {approved, returning}
            # 兼容仅有 status=refunding 但 refund_status 已脱离 applied/reviewing 的订单
            cond = (
                UnifiedOrder.refund_status.in_(["approved", "returning"])
            ) | (
                (UnifiedOrder.status == UnifiedOrderStatus.refunding)
                & (~UnifiedOrder.refund_status.in_(["applied", "reviewing"]))
            )
            return query.where(cond), count_query.where(cond)
        # 已完成 = 退款打款完成
        if sub_tab in ("completed", "refunded"):
            cond = (UnifiedOrder.status == UnifiedOrderStatus.refunded) | (
                UnifiedOrder.refund_status == "refund_success"
            )
            return query.where(cond), count_query.where(cond)
        # 已驳回 = 客服驳回
        if sub_tab == "rejected":
            cond = UnifiedOrder.refund_status == "rejected"
            return query.where(cond), count_query.where(cond)

    return query, count_query


@router.get("")
async def list_unified_orders(
    status: Optional[str] = None,
    refund_status: Optional[str] = None,
    tab: Optional[str] = None,
    sub_tab: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(UnifiedOrder).where(UnifiedOrder.user_id == current_user.id)
    count_query = select(func.count(UnifiedOrder.id)).where(UnifiedOrder.user_id == current_user.id)

    # PRD V2：优先使用 tab 参数（前端 5 Tab + 全部）
    if tab:
        query, count_query = _apply_v2_tab_filter(query, count_query, tab, sub_tab)
    elif status and status != "all":
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
        query.options(selectinload(UnifiedOrder.items), selectinload(UnifiedOrder.store))
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

    # PRD V2：5 Tab 客户端聚合维度 + 12 状态独立维度
    pending_use_v2_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status.in_([
            UnifiedOrderStatus.pending_appointment,
            UnifiedOrderStatus.appointed,
            UnifiedOrderStatus.pending_use,
            UnifiedOrderStatus.partial_used,
        ])
    )
    pending_receipt_v2_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status.in_([
            UnifiedOrderStatus.pending_shipment,
            UnifiedOrderStatus.pending_receipt,
        ])
    )
    completed_v2_q = select(func.count(UnifiedOrder.id)).where(
        base, UnifiedOrder.status.in_([
            UnifiedOrderStatus.completed,
            UnifiedOrderStatus.expired,
        ])
    )
    refund_aftersales_q = select(func.count(UnifiedOrder.id)).where(
        base,
        (UnifiedOrder.status.in_([
            UnifiedOrderStatus.refunding,
            UnifiedOrderStatus.refunded,
        ])) | (UnifiedOrder.refund_status.in_(
            ["applied", "reviewing", "rejected", "returning", "refund_success"]
        )),
    )

    pu_v2 = (await db.execute(pending_use_v2_q)).scalar() or 0
    pr_v2 = (await db.execute(pending_receipt_v2_q)).scalar() or 0
    cp_v2 = (await db.execute(completed_v2_q)).scalar() or 0
    rfa = (await db.execute(refund_aftersales_q)).scalar() or 0

    return {
        # 旧字段（兼容现有客户端）
        "all": total,
        "pending_payment": pp,
        "pending_receipt": pr,
        "pending_use": pu,
        "completed": cp,
        "pending_review": prv,
        "cancelled": cc,
        "refund": rf,
        # PRD V2 新增：5 Tab 聚合维度
        "v2_pending_payment": pp,
        "v2_pending_receipt": pr_v2,
        "v2_pending_use": pu_v2,
        "v2_completed": cp_v2,
        "v2_refund_aftersales": rfa,
    }


@router.get("/{order_id}")
async def get_unified_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items), selectinload(UnifiedOrder.store))
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    # 懒兜底：定时器漏跑时打开详情即时翻 R1/R2
    try:
        from app.tasks.order_status_auto_progress import lazy_progress_order
        if await lazy_progress_order(order, db):
            await db.commit()
    except Exception:  # noqa: BLE001
        pass
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
    has_appointment_set = False
    product_ids_for_check = []
    for item in order.items:
        ft = item.fulfillment_type
        if hasattr(ft, "value"):
            ft = ft.value
        if ft == "delivery":
            has_delivery = True
        else:
            has_in_store = True
        if getattr(item, "appointment_time", None):
            has_appointment_set = True
        product_ids_for_check.append(item.product_id)

    # V2：批量查询商品的 appointment_mode（避免 lazy-load 在 async session 中触发 sync IO）
    # 模型中 appointment_mode 枚举值为 none/date/time_slot/custom_form；
    # 任何非 "none" 值都视为"需要预约"。
    has_appointment_required = False
    if product_ids_for_check:
        prod_rows = await db.execute(
            select(Product.id, Product.appointment_mode).where(
                Product.id.in_(product_ids_for_check)
            )
        )
        for _pid, appt_mode in prod_rows.all():
            mode_val = appt_mode.value if hasattr(appt_mode, "value") else appt_mode
            mode = (mode_val or "").lower()
            if mode and mode != "none":
                has_appointment_required = True
                break

    # [PRD 订单状态机简化方案 v1.0] 状态机推进：
    # 1) 实物 only → pending_shipment
    # 2) 到店 + 需预约且未预约 → pending_appointment
    # 3) 到店 + 需预约且已预约 → **pending_use（直接出码，跳过 appointed）**
    # 4) 其它（普通到店）→ pending_use
    if has_delivery and not has_in_store:
        order.status = UnifiedOrderStatus.pending_shipment
    elif has_in_store:
        if has_appointment_required and not has_appointment_set:
            order.status = UnifiedOrderStatus.pending_appointment
        else:
            # 已设预约 或 不需要预约 → 立即 pending_use（出核销码）
            order.status = UnifiedOrderStatus.pending_use
    else:
        order.status = UnifiedOrderStatus.pending_use

    return {"message": "支付成功", "order_no": order.order_no, "status": _normalize_status(order.status)}


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


# ─────────── PRD V2: 预约相关 ───────────


@router.post("/{order_id}/appointment")
async def set_order_appointment(
    order_id: int,
    data: UnifiedOrderSetAppointmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD 订单状态机简化方案 v1.0] 用户填写预约时间。

    新策略（2026-05-03 起）：
    - 首次填预约日：pending_appointment → **pending_use**（直接跳过 appointed，立即出码）
    - 修改预约日：pending_use 阶段持续允许调整，状态保持不变
    - 兼容历史 appointed：旧订单仍可调用本接口改预约日，状态翻为 pending_use
    """
    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    cur = _normalize_status(order.status)
    if cur not in ("pending_appointment", "appointed", "pending_use"):
        raise HTTPException(status_code=400, detail="该订单当前状态不允许预约")

    # 退款进行中不允许调整预约日
    refund_val = order.refund_status
    if hasattr(refund_val, "value"):
        refund_val = refund_val.value
    if refund_val in ("applied", "reviewing", "approved", "returning", "refund_success"):
        raise HTTPException(status_code=400, detail="该订单退款处理中，暂不允许调整预约时间")

    target_items = order.items
    if data.order_item_id:
        target_items = [it for it in order.items if it.id == data.order_item_id]
        if not target_items:
            raise HTTPException(status_code=404, detail="订单项不存在")

    # 已核销过的订单不允许改预约日（保护核销轨迹）
    any_used = any((it.used_redeem_count or 0) > 0 for it in order.items)
    if cur == "pending_use" and any_used:
        raise HTTPException(status_code=400, detail="该订单已部分核销，无法修改预约时间")

    for it in target_items:
        it.appointment_time = data.appointment_time
        if data.appointment_data is not None:
            it.appointment_data = data.appointment_data
        it.updated_at = datetime.utcnow()

    # 关键变化：直接进入 pending_use（立即出码），跳过 appointed
    order.status = UnifiedOrderStatus.pending_use
    order.updated_at = datetime.utcnow()
    return {
        "message": "预约已确认",
        "status": "pending_use",
        "appointment_time": data.appointment_time.isoformat(),
    }


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

    # PRD F-12：15 天评价时效校验（防绕过前端）
    completed_at = getattr(order, "completed_at", None)
    if completed_at is not None:
        deadline = completed_at + timedelta(days=REVIEW_VALID_DAYS)
        if datetime.utcnow() > deadline:
            raise HTTPException(status_code=400, detail="评价已过期")

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

    has_redemption = any(item.used_redeem_count > 0 for item in order.items)

    refund_req = RefundRequest(
        order_id=order.id,
        order_item_id=data.order_item_id,
        user_id=current_user.id,
        reason=data.reason,
        refund_amount=refund_amount,
        has_redemption=has_redemption,
    )
    db.add(refund_req)

    order.refund_status = RefundStatusEnum.applied
    # PRD V2 退款融合：主状态直接进入 refunding（非 cancelled 时）
    cur = _normalize_status(order.status)
    if cur != "cancelled":
        order.status = UnifiedOrderStatus.refunding
    order.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(refund_req)
    msg = "退款申请已提交"
    if has_redemption:
        msg = "退款申请已提交，该订单存在核销记录，需人工审核"
    return {"message": msg, "refund_id": refund_req.id, "has_redemption": has_redemption}


async def _do_withdraw_refund(order, db: AsyncSession) -> dict:
    """共用撤回核心逻辑（给 /refund/withdraw 与 /refund/cancel 别名两个端点共用）。

    PRD「我的订单与售后状态体系优化」F-13：
    - 仅在售后处于「待审核」（refund_status in {applied, reviewing}）时允许撤销
    - 撤销后订单 status 回到撤销前的合法态：refunding → pending_use（兜底）
    - refund_status 写为 none；保留 RefundRequest 行作为审计（status=withdrawn）
    """
    refund_val = order.refund_status
    if hasattr(refund_val, "value"):
        refund_val = refund_val.value
    if refund_val not in ("applied", "reviewing"):
        raise HTTPException(status_code=400, detail="当前售后状态不允许撤销")

    refund_result = await db.execute(
        select(RefundRequest)
        .where(
            RefundRequest.order_id == order.id,
            RefundRequest.status.in_([
                RefundRequestStatus.pending,
                RefundRequestStatus.reviewing,
            ]),
        )
        .order_by(RefundRequest.created_at.desc())
    )
    refund_req = refund_result.scalar_one_or_none()
    if refund_req:
        refund_req.status = RefundRequestStatus.withdrawn
        refund_req.updated_at = datetime.utcnow()

    order.refund_status = RefundStatusEnum.none
    # PRD V2：退款撤回回到 pending_use（实物订单可由商家手动改为 pending_receipt）
    if _normalize_status(order.status) == "refunding":
        order.status = UnifiedOrderStatus.pending_use
    order.updated_at = datetime.utcnow()

    await db.flush()
    return {"message": "退款申请已撤回"}


@router.post("/{order_id}/refund/withdraw")
async def withdraw_refund(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder).where(
            UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return await _do_withdraw_refund(order, db)


@router.post("/{order_id}/refund/cancel")
async def cancel_refund(
    order_id: int,
    data: Optional[UnifiedOrderRefundCancelRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD F-13 别名端点：用户撤销售后申请。

    与 /refund/withdraw 等价，仅在售后处于「待审核」时允许；
    便于前端语义化使用：用户视角是"撤销申请"而非"撤回"。
    """
    result = await db.execute(
        select(UnifiedOrder).where(
            UnifiedOrder.id == order_id, UnifiedOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return await _do_withdraw_refund(order, db)
