import logging
import os
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
    FulfillmentType,
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
    UserAddress,
    UserCoupon,
    UserCouponStatus,
)
from app.utils.time_slots import appointment_to_slot as _appt_to_slot
from app.schemas.unified_orders import (
    ALLOWED_PAYMENT_METHODS,
    PAYMENT_METHOD_TEXT_MAP,
    ConfirmFreeRequest,
    OrderItemResponse,
    UnifiedOrderCancelRequest,
    UnifiedOrderCreate,
    UnifiedOrderPayRequest,
    UnifiedOrderRefundRequest,
    UnifiedOrderRefundCancelRequest,
    normalize_payment_method,
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


def _norm_fulfillment(value) -> str:
    """规范化 fulfillment_type，返回 enum value 字符串。"""
    if value is None:
        return ""
    if hasattr(value, "value"):
        return value.value
    return str(value)


# [上门服务履约 PRD v1.0 · F4] 双层名额校验：占用名额的订单状态范围
# 已支付/已预约/待核销/部分核销/待评价/已完成 计入；已取消、已退款不计入
QUOTA_OCCUPY_STATUSES = [
    UnifiedOrderStatus.pending_payment,
    UnifiedOrderStatus.pending_shipment,
    UnifiedOrderStatus.pending_receipt,
    UnifiedOrderStatus.pending_appointment,
    UnifiedOrderStatus.appointed,
    UnifiedOrderStatus.pending_use,
    UnifiedOrderStatus.partial_used,
    UnifiedOrderStatus.pending_review,
    UnifiedOrderStatus.completed,
]


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
    # [核销订单过期+改期规则优化 v1.0] 所有状态下「联系商家」按钮始终展示
    if "contact_store" not in btns:
        btns.append("contact_store")
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


def _build_payment_method_text(order) -> Optional[str]:
    """[支付配置 PRD v1.0] 构造 payment_method_text："{显示名称}（{端名}）"。

    端名映射：wechat_miniprogram→小程序 / wechat_app/alipay_app→APP / alipay_h5→H5。

    [2026-05-05 H5 订单详情"支付方式"显示错误（优惠券全额抵扣场景）Bug 修复 v1.0]
    判断顺序调整为「以实付方式为准，预选通道仅作通道补充」：
      1. 若 payment_method 属于"非真实通道"（coupon_deduction / balance / points），
         即使预选通道字段（payment_channel_code/payment_display_name）非空也忽略，
         直接返回中文兜底文案，避免 0 元单仍显示"支付宝（H5）"。
      2. 若 payment_method ∈ {wechat, alipay} 且 code+name 齐备，按"显示名（端名）"拼接。
      3. payment_method 存在但缺 code/name 时，使用中文兜底。
      4. 兼容历史/异常路径：仅用 name 兜底。
      5. 全部缺失返回 None。
    """
    PLATFORM_LABEL = {
        "wechat_miniprogram": "小程序",
        "wechat_app": "APP",
        "alipay_h5": "H5",
        "alipay_app": "APP",
    }
    NON_CHANNEL_PMS = {"coupon_deduction", "balance", "points"}

    pm_val = getattr(order, "payment_method", None)
    if hasattr(pm_val, "value"):
        pm_val = pm_val.value
    pm_val = str(pm_val) if pm_val is not None else None

    # 第 1 优先级：非真实通道支付（0 元单 / 余额 / 积分）
    if pm_val in NON_CHANNEL_PMS:
        return PAYMENT_METHOD_TEXT_MAP.get(pm_val)

    code = getattr(order, "payment_channel_code", None)
    name = getattr(order, "payment_display_name", None)

    # 第 2 优先级：真实通道支付（wechat / alipay），且 code+name 齐备
    if pm_val in {"wechat", "alipay"} and code and name:
        suffix = PLATFORM_LABEL.get(code)
        if suffix:
            return f"{name}（{suffix}）"
        return name

    # 第 3 优先级：payment_method 存在但 code/name 缺失，按枚举中文兜底
    if pm_val:
        text = PAYMENT_METHOD_TEXT_MAP.get(pm_val)
        if text:
            return text

    # 第 4 优先级：兼容历史/异常路径——仅用 name 兜底
    if name:
        return name
    return None


def _build_order_response(order) -> UnifiedOrderResponse:
    resp = UnifiedOrderResponse.model_validate(order)
    # [修改预约 Bug 修复 v1.0] 把 OrderItem.product.appointment_mode 透传到响应 item 中
    # 前端三端（H5 / 小程序 / Flutter）会根据该字段联动：
    #   - none      → 不显示"修改预约"按钮（保持现状逻辑）
    #   - date      → 弹窗内仅显示日期选择，隐藏整块时段
    #   - time_slot → 弹窗显示日期 + 3 列时段
    #   - custom_form → 跳转/拉起自定义预约表单页面
    try:
        items_by_id = {it.id: it for it in (order.items or [])}
        for resp_item in resp.items:
            src = items_by_id.get(resp_item.id)
            if src is None:
                continue
            prod = getattr(src, "product", None)
            if prod is None:
                continue
            mode_val = getattr(prod, "appointment_mode", None)
            if hasattr(mode_val, "value"):
                mode_val = mode_val.value
            resp_item.appointment_mode = (mode_val or "none")
            resp_item.custom_form_id = getattr(prod, "custom_form_id", None)
    except Exception:  # noqa: BLE001
        # 透传字段失败不应阻断整个订单详情；保持向后兼容
        pass
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
    # [2026-05-04 订单「联系商家」电话不显示 Bug 修复 v1.0]
    # 必须把 order.store_id 透传给前端：H5/小程序/Flutter 三端的「联系商家」弹窗
    # 都依赖 storeId 调用 /api/stores/{id}/contact，缺失时直接 return 不发请求。
    resp.store_id = order.store_id
    resp.store_name = order.store.store_name if order.store else None

    # [2026-05-05 订单页地址导航按钮 PRD v1.0] 透传门店完整地址 + 经纬度
    # 用于客户端「订单明细页」给门店地址行展示「导航」按钮，
    # 经纬度缺失时由客户端走文字地址降级（PRD F-08）。
    try:
        if order.store is not None:
            store_obj = order.store
            # MerchantStore 模型: address/lat/lng/province/city/district
            base_addr = (
                getattr(store_obj, "address", None)
                or getattr(store_obj, "store_address", None)
                or ""
            )
            province = getattr(store_obj, "province", None) or ""
            city = getattr(store_obj, "city", None) or ""
            district = getattr(store_obj, "district", None) or ""
            full_addr = f"{province}{city}{district}{base_addr}".strip()
            resp.store_address = full_addr or (base_addr or None)
            store_lat = getattr(store_obj, "lat", None) or getattr(store_obj, "latitude", None)
            store_lng = getattr(store_obj, "lng", None) or getattr(store_obj, "longitude", None)
            resp.store_lat = float(store_lat) if store_lat is not None else None
            resp.store_lng = float(store_lng) if store_lng is not None else None
            # [订单详情页订单地址展示统一 Bug 修复 v1.0]
            # 商家后台「到店核销订单」详情需展示门店联系电话，从 MerchantStore.contact_phone 透传
            store_phone = getattr(store_obj, "contact_phone", None)
            if store_phone:
                resp.store_phone = str(store_phone)
    except Exception:  # noqa: BLE001
        # 透传失败不阻塞订单主流程
        pass

    # [2026-05-05 订单页地址导航按钮 PRD v1.0] 收货/上门地址全文（导航按钮文字降级用）
    try:
        # 1) 上门地址：优先用 service_address_snapshot 快照
        snap = getattr(order, "service_address_snapshot", None)
        if snap and isinstance(snap, dict):
            province = snap.get("province") or ""
            city = snap.get("city") or ""
            district = snap.get("district") or ""
            street = snap.get("street") or snap.get("detail") or ""
            text = f"{province}{city}{district}{street}".strip()
            if text:
                resp.shipping_address_text = text
            resp.shipping_address_name = snap.get("name") or None
            resp.shipping_address_phone = snap.get("phone") or None
        # 2) 收货地址：从关联表读取（订单创建后地址簿原条目仍可读，无快照表也能拿到当前值）
        if not resp.shipping_address_text:
            ship_addr = getattr(order, "shipping_address", None)
            if ship_addr is not None:
                province = getattr(ship_addr, "province", "") or ""
                city = getattr(ship_addr, "city", "") or ""
                district = getattr(ship_addr, "district", "") or ""
                street = getattr(ship_addr, "street", "") or ""
                text = f"{province}{city}{district}{street}".strip()
                if text:
                    resp.shipping_address_text = text
                if not resp.shipping_address_name:
                    resp.shipping_address_name = getattr(ship_addr, "name", None)
                if not resp.shipping_address_phone:
                    resp.shipping_address_phone = getattr(ship_addr, "phone", None)
    except Exception:  # noqa: BLE001
        pass

    # ──────────────────────────────────────────────────────────────────
    # [订单详情页订单地址展示统一 Bug 修复 v1.0]
    # 按订单类型（fulfillment_type）下发结构化的 order_address 字段：
    #   - 到店核销 (in_store)：order_address = None（用户端隐藏【订单地址】区块，
    #     信息已在【预约信息·预约门店】中体现；商家端会用 store_id/store_name/store_address
    #     单独渲染门店地址区块，本字段保持 None 避免与其重复或矛盾）
    #   - 配送/快递 (delivery)：收件人 + 电话 + 完整收货地址
    #   - 上门服务 (on_site / onsite_service)：联系人 + 电话 + 完整上门地址
    # 多端共用同一接口数据，确保用户端、商家端展示一致。
    # 注意：本字段「与订单类型一一对应」，由后端按 OrderItem.fulfillment_type 唯一决定，
    # 避免前端各端各自判断订单类型导致的逻辑分散与口径不一致。
    # ──────────────────────────────────────────────────────────────────
    try:
        ft_set: set[str] = set()
        for it in (order.items or []):
            ft_val = getattr(it, "fulfillment_type", None)
            if hasattr(ft_val, "value"):
                ft_val = ft_val.value
            if ft_val:
                ft_set.add(str(ft_val))

        # 优先级：on_site > delivery > in_store
        # 真实业务里同一笔订单的多个 item 通常履约类型一致；
        # 若混合订单出现（极少），按"非到店"优先，确保配送/上门的地址字段不会丢。
        oa_type: Optional[str] = None
        if "on_site" in ft_set or "onsite_service" in ft_set:
            oa_type = "onsite_service"
        elif "delivery" in ft_set:
            oa_type = "delivery"
        elif "in_store" in ft_set:
            oa_type = "store"

        if oa_type == "delivery" or oa_type == "onsite_service":
            text = (resp.shipping_address_text or "") if isinstance(resp.shipping_address_text, str) else (resp.shipping_address_text or "")
            name = resp.shipping_address_name
            phone = resp.shipping_address_phone
            # 仅当至少有"地址文字"或"姓名/电话"中一项时才下发，避免空 order_address
            if text or name or phone:
                resp.order_address = {
                    "type": oa_type,
                    "contact_name": name,
                    "contact_phone": phone,
                    "address_text": text,
                    "store_id": None,
                    "ext": None,
                }
                resp.order_address_type = oa_type
            else:
                resp.order_address = None
                resp.order_address_type = oa_type
        elif oa_type == "store":
            # 到店核销：order_address 不下发结构化地址数据；
            # 商家端通过 store_id/store_name/store_address/store_lat/store_lng 单独渲染。
            resp.order_address = None
            resp.order_address_type = "store"
    except Exception:  # noqa: BLE001
        # 任何异常都不阻塞订单详情主流程；前端仍可基于旧字段兜底
        resp.order_address = None
        resp.order_address_type = None

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
    # [支付配置 PRD v1.0] payment_method_text
    resp.payment_method_text = _build_payment_method_text(order)

    # [核销订单过期+改期规则优化 v1.0] reschedule_count/limit + allow_reschedule
    resp.reschedule_count = int(getattr(order, "reschedule_count", 0) or 0)
    resp.reschedule_limit = int(getattr(order, "reschedule_limit", 3) or 3)
    # allow_reschedule 取自关联商品；若任一商品禁止改期，则整单视为不允许
    try:
        prods_allow: list[bool] = []
        for it in (order.items or []):
            prod = getattr(it, "product", None)
            if prod is not None:
                v = getattr(prod, "allow_reschedule", True)
                prods_allow.append(True if v is None else bool(v))
        resp.allow_reschedule = (all(prods_allow) if prods_allow else True)
    except Exception:  # noqa: BLE001
        resp.allow_reschedule = True

    # [核销订单过期+改期规则优化 v1.0] 已改期 ≥ 上限：把 modify_appointment 按钮改为占位并附 reschedule_block badge
    if resp.reschedule_count >= resp.reschedule_limit and "modify_appointment" in resp.action_buttons:
        # 保持按钮位置（前端置灰），但添加一个 badge 让前端识别
        if "reschedule_blocked" not in resp.badges:
            resp.badges.append("reschedule_blocked")
    return resp


def _generate_order_no() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.digits, k=6))
    return f"UO{ts}{rand}"


def _normalize_id_list(raw) -> set[int]:
    """[优惠券下单页 Bug 修复 v2] 把 coupon.scope_ids（JSON / list / 逗号分隔字符串）统一转为 {int} 集合。"""
    out: set[int] = set()
    if raw is None:
        return out
    if isinstance(raw, list):
        for x in raw:
            try:
                out.add(int(x))
            except (TypeError, ValueError):
                continue
    elif isinstance(raw, str):
        for x in raw.split(","):
            x = x.strip()
            if not x:
                continue
            try:
                out.add(int(x))
            except (TypeError, ValueError):
                continue
    elif isinstance(raw, dict):
        # 兼容 {"ids": [...]} 这种历史结构
        ids = raw.get("ids") if isinstance(raw, dict) else None
        if isinstance(ids, list):
            for x in ids:
                try:
                    out.add(int(x))
                except (TypeError, ValueError):
                    continue
    return out


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

    # [2026-05-04 支付通道枚举不一致 Bug 修复 v1.0]
    # 双保险：schema 已做 field_validator 归一化，这里再兜底校验一次。
    # 经过 schema 之后 data.payment_method 应当只可能是 wechat / alipay / None。
    # 若拿到非法值（理论上不会发生，除非走了绕过 schema 的内部调用），直接 400。
    if data.payment_method is not None and data.payment_method not in ALLOWED_PAYMENT_METHODS:
        normalized = normalize_payment_method(data.payment_method)
        if normalized is None:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的支付方式：{data.payment_method}",
            )
        data.payment_method = normalized

    product_ids = [item.product_id for item in data.items]
    result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products_map = {p.id: p for p in result.scalars().all()}

    # ── [上门服务履约 PRD v1.0 · F5] 上门服务必填地址 ──
    # 任一商品 fulfillment_type=on_site 时，service_address_id 必传且必须属于当前用户
    has_on_site = any(
        _norm_fulfillment(p.fulfillment_type) == "on_site"
        for p in products_map.values()
    )
    service_address_obj: Optional[UserAddress] = None
    service_address_snapshot_data: Optional[dict] = None
    if has_on_site:
        if not data.service_address_id:
            raise HTTPException(status_code=400, detail="上门服务订单必须选择上门地址")
        addr_res = await db.execute(
            select(UserAddress).where(
                UserAddress.id == data.service_address_id,
                UserAddress.user_id == current_user.id,
            )
        )
        service_address_obj = addr_res.scalar_one_or_none()
        if not service_address_obj:
            raise HTTPException(status_code=400, detail="所选上门地址不存在或不属于当前用户")
        service_address_snapshot_data = {
            "address_id": service_address_obj.id,
            "name": service_address_obj.name,
            "phone": service_address_obj.phone,
            "province": service_address_obj.province,
            "city": service_address_obj.city,
            "district": service_address_obj.district,
            "street": service_address_obj.street,
            "detail": service_address_obj.street,
            "snapshot_at": datetime.utcnow().isoformat(),
        }

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
        # ── [2026-05-05 H5 优惠券抵扣 0 元下单 Bug 修复 v1.2 · R4] ──
        # 历史脏数据 / 旧代码并发漏洞导致同一 (user_id, coupon_id, unused) 可能
        # 出现多条记录，原先的 scalar_one_or_none() 会抛 MultipleResultsFound → 500。
        # 这里改为按 id ASC 取最早领的那张（对用户最公平的口径），
        # 既容错脏数据，又不阻塞下单。
        # 注意：MySQL 不支持 PostgreSQL 的 NULLS LAST 语法，所以仅用 id 排序。
        uc_result = await db.execute(
            select(UserCoupon)
            .where(
                UserCoupon.user_id == current_user.id,
                UserCoupon.coupon_id == data.coupon_id,
                UserCoupon.status == UserCouponStatus.unused,
            )
            .order_by(UserCoupon.id.asc())
        )
        _uc_rows = uc_result.scalars().all()
        if len(_uc_rows) > 1:
            try:
                import logging as _log_uc
                _log_uc.getLogger(__name__).warning(
                    "[unified_orders] duplicate user_coupons detected: user_id=%s coupon_id=%s count=%s ids=%s",
                    current_user.id, data.coupon_id, len(_uc_rows), [r.id for r in _uc_rows],
                )
            except Exception:
                pass
        user_coupon = _uc_rows[0] if _uc_rows else None
        if not user_coupon:
            raise HTTPException(status_code=400, detail="优惠券不可用")

        # ── [优惠券下单页 Bug 修复 v2 · 兜底校验] ──
        # 防止前端绕过 /api/coupons/usable-for-order 直接传不适用的 coupon_id。
        # 这里再做一次：过期 / 已下架 / 适用范围（scope=product/category）/ 排除商品 全部校验。
        now_dt = datetime.utcnow()
        if user_coupon.expire_at is not None and user_coupon.expire_at <= now_dt:
            raise HTTPException(status_code=422, detail="优惠券已过期，不适用本单")

        coupon_result = await db.execute(select(Coupon).where(Coupon.id == data.coupon_id))
        coupon = coupon_result.scalar_one_or_none()
        if coupon:
            # 已下架券不允许新下单使用
            if getattr(coupon, "is_offline", False):
                raise HTTPException(status_code=422, detail="该优惠券已下架，不适用本单")
            coupon_status = coupon.status.value if hasattr(coupon.status, "value") else coupon.status
            if coupon_status != "active":
                raise HTTPException(status_code=422, detail="该优惠券已停用，不适用本单")

            # 适用范围校验
            scope_val = coupon.scope.value if hasattr(coupon.scope, "value") else coupon.scope
            if scope_val == "product":
                allowed_pids = _normalize_id_list(coupon.scope_ids)
                order_pids = {oi["product"].id for oi in order_items}
                if not allowed_pids or not (order_pids & allowed_pids):
                    raise HTTPException(status_code=422, detail="优惠券不适用本单（指定商品）")
            elif scope_val == "category":
                allowed_cids = _normalize_id_list(coupon.scope_ids)
                order_cids = {getattr(oi["product"], "category_id", None) for oi in order_items}
                order_cids.discard(None)
                if not allowed_cids or not (order_cids & allowed_cids):
                    raise HTTPException(status_code=422, detail="优惠券不适用本单（指定分类）")

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

            coupon_type = coupon.type
            if hasattr(coupon_type, "value"):
                coupon_type = coupon_type.value

            # ── [B1 修复] 免费试用券：整单 0 元抵扣，不受 condition_amount 影响 ──
            # free_trial 本质是"凭券免费试用"，必须强制把可享券金额抵扣到 0。
            if coupon_type == "free_trial":
                coupon_discount = eligible_amount
            elif eligible_amount >= float(coupon.condition_amount or 0):
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

    # [2026-05-04 H5 优惠券抵扣 0 元下单 Bug 修复 v1.0 · B1]
    # Server-side 兜底（最后一道防线，独立于前端各端是否已修复）：
    # 当 paid_amount == 0 时，强制把 payment_method 改写为 coupon_deduction。
    # 这能覆盖以下场景：
    #   1) 老客户端尚未升级，仍传 alipay/wechat 但实付为 0
    #   2) 直接通过 Postman / 第三方脚本绕过前端构造的 0 元请求
    #   3) 积分抵扣到 0 元（按用户决策口径 A，统一记 coupon_deduction）
    _final_payment_method = data.payment_method
    if float(paid_amount) == 0:
        if _final_payment_method != UnifiedPaymentMethod.coupon_deduction.value:
            logger.info(
                "[server-side override] paid_amount=0 → payment_method "
                "forced to coupon_deduction (user_id=%s, original=%s)",
                current_user.id,
                _final_payment_method,
            )
        _final_payment_method = UnifiedPaymentMethod.coupon_deduction.value

    order = UnifiedOrder(
        order_no=_generate_order_no(),
        user_id=current_user.id,
        total_amount=total_amount,
        paid_amount=paid_amount,
        points_deduction=points_deduction,
        # [2026-05-04 H5 优惠券抵扣 0 元下单 Bug 修复 v1.0 · B1] 0 元单已在上方被兜底为 coupon_deduction
        payment_method=_final_payment_method,
        coupon_id=data.coupon_id,
        coupon_discount=coupon_discount,
        shipping_address_id=data.shipping_address_id,
        # [上门服务履约 PRD v1.0 · F5] 上门地址 + 快照
        service_address_id=(service_address_obj.id if service_address_obj else None),
        service_address_snapshot=service_address_snapshot_data,
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
        # ── [预约日期模式 Bug 修复 v1.0] date 模式忽略 time_slot ──
        # date 模式按设计仅按"天"维度限流，根本不需要时段。
        # 若前端误传 appointment_data.time_slot，后端主动从字典里删掉，避免脏值入库。
        if appt_mode == "date":
            appt_data_in = getattr(item_d, "appointment_data", None)
            if isinstance(appt_data_in, dict) and "time_slot" in appt_data_in:
                logger.info(
                    "[date_mode] 商品 %s 为预约日期模式，已忽略前端误传的 time_slot=%r",
                    product.id, appt_data_in.get("time_slot"),
                )
                appt_data_in.pop("time_slot", None)
                item_d.appointment_data = appt_data_in
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

            # ════════════════════════════════════════════════════════════
            # [上门服务履约 PRD v1.0 · F4] 双层名额校验（商品级 + 门店级）
            # 1) 商品级：按时段 → product.time_slots[该时段].capacity
            #            按天   → product.daily_capacity（复用 product.daily_quota）
            # 2) 门店级：所有商品累计同一时段（或同一天）下单数 < store.slot_capacity
            # 占用名额状态：QUOTA_OCCUPY_STATUSES（已取消/已退款不计入）
            # 仅在两层都通过时放行；任一不通过返回友好错误。
            # ════════════════════════════════════════════════════════════
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
                    store_capacity = int(getattr(target_store, "slot_capacity", 0) or 0) if target_store else 0
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

                    # ── 商品级名额（按时段：product.time_slots[selected].capacity） ──
                    product_slot_cap: Optional[int] = None
                    p_slots = getattr(product, "time_slots", None)
                    if isinstance(p_slots, list):
                        for s in p_slots:
                            if not isinstance(s, dict):
                                continue
                            s_start = s.get("start") or ""
                            s_end = s.get("end") or ""
                            label = s.get("label") or ""
                            slot_str = f"{s_start}-{s_end}" if s_start and s_end else label
                            if slot_str == selected_slot or label == selected_slot:
                                cap_val = s.get("capacity")
                                if cap_val is not None:
                                    try:
                                        cap_int = int(cap_val)
                                        if cap_int > 0:
                                            product_slot_cap = cap_int
                                    except (TypeError, ValueError):
                                        pass
                                break

                    fifteen_min_ago = datetime.utcnow() - timedelta(minutes=15)
                    occupy_filter = (
                        (UnifiedOrder.status.in_(QUOTA_OCCUPY_STATUSES[1:]))  # 排除 pending_payment 在外的所有占用态
                        | (
                            (UnifiedOrder.status == UnifiedOrderStatus.pending_payment)
                            & (UnifiedOrder.created_at >= fifteen_min_ago)
                        )
                    )

                    # 商品级校验
                    if product_slot_cap is not None and product_slot_cap > 0:
                        booked_q = await db.execute(
                            select(func.count(OrderItem.id))
                            .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
                            .where(
                                OrderItem.product_id == product.id,
                                func.date(OrderItem.appointment_time) == q_date,
                                func.json_extract(OrderItem.appointment_data, "$.time_slot") == selected_slot,
                                occupy_filter,
                            )
                        )
                        booked_count = booked_q.scalar() or 0
                        if booked_count >= product_slot_cap:
                            raise HTTPException(
                                status_code=400,
                                detail="该商品当前时段已约满，请选择其他时段或商品",
                            )

                    # 门店级校验（跨所有商品在该门店同一时段累计）
                    if store_capacity > 0:
                        booked_q = await db.execute(
                            select(func.count(OrderItem.id))
                            .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
                            .where(
                                func.date(OrderItem.appointment_time) == q_date,
                                func.json_extract(OrderItem.appointment_data, "$.time_slot") == selected_slot,
                                UnifiedOrder.store_id == target_store_id,
                                occupy_filter,
                            )
                        )
                        booked_count = booked_q.scalar() or 0
                        if booked_count >= store_capacity:
                            raise HTTPException(
                                status_code=400,
                                detail="该门店当前时段已约满，请选择其他时段",
                            )

            # ── 按天预约的双层名额校验（appt_mode=date） ──
            if appt_mode == "date" and selected_date_str and target_store_id:
                try:
                    q_date2 = date.fromisoformat(selected_date_str)
                except (ValueError, TypeError):
                    q_date2 = None
                if q_date2:
                    store_res2 = await db.execute(
                        select(MerchantStore).where(MerchantStore.id == target_store_id)
                    )
                    target_store2 = store_res2.scalar_one_or_none()
                    store_capacity2 = int(getattr(target_store2, "slot_capacity", 0) or 0) if target_store2 else 0
                    product_daily_cap: Optional[int] = None
                    daily_q = getattr(product, "daily_quota", None)
                    if daily_q is not None:
                        try:
                            d_int = int(daily_q)
                            if d_int > 0:
                                product_daily_cap = d_int
                        except (TypeError, ValueError):
                            pass

                    fifteen_min_ago2 = datetime.utcnow() - timedelta(minutes=15)
                    occupy_filter2 = (
                        (UnifiedOrder.status.in_(QUOTA_OCCUPY_STATUSES[1:]))
                        | (
                            (UnifiedOrder.status == UnifiedOrderStatus.pending_payment)
                            & (UnifiedOrder.created_at >= fifteen_min_ago2)
                        )
                    )

                    if product_daily_cap is not None and product_daily_cap > 0:
                        booked_q = await db.execute(
                            select(func.count(OrderItem.id))
                            .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
                            .where(
                                OrderItem.product_id == product.id,
                                func.date(OrderItem.appointment_time) == q_date2,
                                occupy_filter2,
                            )
                        )
                        booked_count = booked_q.scalar() or 0
                        if booked_count >= product_daily_cap:
                            raise HTTPException(
                                status_code=400,
                                detail="该商品当日名额已约满，请选择其他日期或商品",
                            )

                    if store_capacity2 > 0:
                        booked_q = await db.execute(
                            select(func.count(OrderItem.id))
                            .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
                            .where(
                                func.date(OrderItem.appointment_time) == q_date2,
                                UnifiedOrder.store_id == target_store_id,
                                occupy_filter2,
                            )
                        )
                        booked_count = booked_q.scalar() or 0
                        if booked_count >= store_capacity2:
                            raise HTTPException(
                                status_code=400,
                                detail="该门店当日名额已约满，请选择其他日期",
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
        # ── [2026-05-05 H5 优惠券抵扣 0 元下单 Bug 修复 v1.2 · R4] ──
        # 与上方校验段保持同一排序口径，确保校验/核销命中同一条 user_coupon 记录。
        # 注意：MySQL 不支持 NULLS LAST，所以仅按 id ASC 排序。
        uc_result2 = await db.execute(
            select(UserCoupon).where(
                UserCoupon.user_id == current_user.id,
                UserCoupon.coupon_id == data.coupon_id,
                UserCoupon.status == UserCouponStatus.unused,
            )
            .order_by(UserCoupon.id.asc())
        )
        uc = uc_result2.scalars().first()
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

    # [PRD-01 全平台固定时段切片体系 v1.0 · F-01-3]
    # 下单时根据首个有 appointment_time 的 item 计算订单级 time_slot（1-9）。
    # · 跨日订单（22:00-次日 00:00）按起始时间归段（PRD R-01-03）
    # · 凌晨段 / 无预约时间订单 / 先下单后预约 → time_slot = NULL（PRD R-01-04）
    _first_appt_time = None
    for _it in data.items:
        _appt = getattr(_it, "appointment_time", None)
        if _appt:
            _first_appt_time = _appt
            break
    order.time_slot = _appt_to_slot(_first_appt_time) if _first_appt_time else None

    # [订单核销码状态与未支付超时治理 v1.0]
    # 站内信文案中的 X 改为读全局 settings.PAYMENT_TIMEOUT_MINUTES，
    # 与"未支付超时自动取消"定时任务保持长期一致。
    from app.core.config import settings as _app_settings
    _payment_timeout_min = int(getattr(_app_settings, "PAYMENT_TIMEOUT_MINUTES", 15) or 15)
    notification = Notification(
        user_id=current_user.id,
        title="订单创建成功",
        content=f"您的订单 {order.order_no} 已创建，请在{_payment_timeout_min}分钟内完成支付。",
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


@router.get("/sandbox-confirm")
async def sandbox_confirm(
    order_no: str = Query(..., description="订单号"),
    channel: Optional[str] = Query(None, description="通道编码（仅日志用）"),
    db: AsyncSession = Depends(get_db),
):
    """[H5 支付链路修复 v1.0] 支付宝 H5 沙盒回跳入口。

    本接口**仅用于开发自测**：前端沙盒收银台页提交"模拟支付成功"后调用此接口，
    将订单按状态机推进为已支付（复用 `_advance_status_after_payment`）。
    生产环境替换为真实支付回调后此接口可下线。

    不做用户身份校验（沙盒），但会校验：
      - 订单存在（否则 404）
      - 订单状态为 pending_payment（否则 400）

    注意：此路由必须注册在 `/{order_id}` 之前，否则会被 path 参数捕获。
    """
    result = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.order_no == order_no)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "pending_payment":
        raise HTTPException(status_code=400, detail="该订单无法确认支付")

    order.paid_at = datetime.utcnow()
    await _advance_status_after_payment(order, db)
    order.updated_at = datetime.utcnow()

    return {
        "message": "沙盒支付确认成功",
        "id": order.id,
        "order_no": order.order_no,
        "status": _normalize_status(order.status),
    }


@router.get("/{order_id}")
async def get_unified_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UnifiedOrder)
        # [修改预约 Bug 修复 v1.0] 链式预加载 items.product，便于响应里透传 appointment_mode
        .options(
            selectinload(UnifiedOrder.items).selectinload(OrderItem.product),
            selectinload(UnifiedOrder.store),
        )
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


async def _advance_status_after_payment(order: UnifiedOrder, db: AsyncSession) -> None:
    """[H5 支付链路修复 v1.0] 抽取自 pay_unified_order 的状态推进逻辑。

    被 `pay_unified_order`、`confirm_free_unified_order`、`sandbox_confirm` 三处复用，
    避免状态机分裂。需要 order.items 已通过 selectinload 加载好。

    [PRD 订单状态机简化方案 v1.0] 状态机推进：
    1) 实物 only → pending_shipment
    2) 到店 + 需预约且未预约 → pending_appointment
    3) 到店 + 需预约且已预约 → **pending_use（直接出码，跳过 appointed）**
    4) 其它（普通到店）→ pending_use
    """
    has_delivery = False
    has_in_store = False
    has_appointment_set = False
    product_ids_for_check: list[int] = []
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

    if has_delivery and not has_in_store:
        order.status = UnifiedOrderStatus.pending_shipment
    elif has_in_store:
        if has_appointment_required and not has_appointment_set:
            order.status = UnifiedOrderStatus.pending_appointment
        else:
            order.status = UnifiedOrderStatus.pending_use
    else:
        order.status = UnifiedOrderStatus.pending_use


def _build_sandbox_pay_url(order_no: str, channel_code: str) -> Optional[str]:
    """[支付宝 H5 正式接入 v1.0 · 已废弃 deprecated]

    历史沙盒桩，仅在真实支付宝 SDK 装配失败时作为兜底使用，避免 alipay_h5 通道
    因为依赖缺失而完全不可用。生产链路已切到 _build_alipay_h5_pay_url。
    """
    base = ""
    try:
        from app.core.config import settings as _settings
        base = getattr(_settings, "PROJECT_BASE_URL", "") or ""
    except Exception:  # noqa: BLE001
        base = ""
    if not base:
        base = os.getenv("PROJECT_BASE_URL", "") or os.getenv("PUBLIC_API_BASE_URL", "")
    base = (base or "").rstrip("/")
    return f"{base}/sandbox-pay?order_no={order_no}&channel={channel_code}"


def _project_base_url() -> str:
    """读取项目对外 base url（含 H5 basePath 前缀），用于拼 return_url / notify_url。"""
    base = ""
    try:
        from app.core.config import settings as _settings
        base = getattr(_settings, "PROJECT_BASE_URL", "") or ""
    except Exception:  # noqa: BLE001
        base = ""
    if not base:
        base = os.getenv("PROJECT_BASE_URL", "") or os.getenv("PUBLIC_API_BASE_URL", "")
    return (base or "").rstrip("/")


def _api_base_url() -> str:
    """notify_url 所用 base：优先 PUBLIC_API_BASE_URL（与 H5 同前缀），用作 /api/...
    路由的对外可达根。
    """
    base = os.getenv("PUBLIC_API_BASE_URL", "") or _project_base_url()
    return (base or "").rstrip("/")


async def _build_alipay_h5_pay_url(order: UnifiedOrder, db: AsyncSession) -> str:
    """[支付宝 H5 正式接入 v1.0 · 核心改动]

    调用真实 alipay.trade.wap.pay，返回 https://openapi.alipay.com/gateway.do?...
    形式的真实收银台 URL。

    异常时抛出 RuntimeError，由调用方捕获后兜底回退到沙盒桩并打告警日志。
    """
    from app.services.alipay_service import (
        create_wap_pay_url,
        get_alipay_client_for_channel,
    )

    client, _ch = await get_alipay_client_for_channel(db, channel_code="alipay_h5")

    project_base = _project_base_url()
    api_base = _api_base_url()
    return_url = f"{project_base}/pay/success?orderId={order.id}&orderNo={order.order_no}"
    notify_url = f"{api_base}/api/payment/alipay/notify"

    # 订单标题：取首项商品名（截断 256 字节）
    subject = "订单"
    try:
        if order.items:
            subject = (order.items[0].product_name or "订单")
    except Exception:  # noqa: BLE001
        subject = "订单"

    total_amount = float(order.paid_amount or order.total_amount or 0)
    if total_amount <= 0:
        raise ValueError("订单金额为 0，不应走支付宝 H5 真实支付")

    pay_url = create_wap_pay_url(
        client,
        out_trade_no=order.order_no,
        total_amount=total_amount,
        subject=subject,
        return_url=return_url,
        notify_url=notify_url,
        timeout_express="30m",
    )
    return pay_url


@router.post("/{order_id}/pay")
async def pay_unified_order(
    order_id: int,
    data: UnifiedOrderPayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """统一订单支付（已移除真实支付接入，目前为状态机推进 + 桩 URL）。

    [H5 支付链路修复 v1.0] 返回字段 `pay_url`：
        当 channel_code=alipay_h5 且 provider=alipay 时，构造一个沙盒收银台 URL
        指向前端 H5 的 /sandbox-pay 页；其它通道（wechat_app / alipay_app /
        wechat_miniprogram）pay_url=None，前端走原生 SDK 通道。
        **此处的 pay_url 是开发自测桩，待真实商户证书接入后替换为支付宝 SDK
        生成的真实收银台 URL。**
    """
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

    # [2026-05-04 支付通道枚举不一致 Bug 修复 v1.0]
    # /pay 接口的 payment_method 同样必须是 provider 级别（wechat / alipay），
    # 老前端可能仍然传通道编码（如 alipay_h5），统一归一化。
    _normalized_pm = normalize_payment_method(data.payment_method)
    if _normalized_pm is None:
        raise HTTPException(
            status_code=400, detail=f"不支持的支付方式：{data.payment_method}"
        )
    order.payment_method = _normalized_pm
    # 注意：paid_at 仅在「真正完成支付」时才写。对于 alipay_h5 真实链路，
    # 等待支付宝异步通知 TRADE_SUCCESS 后再写；其余通道（沙盒桩/微信等）
    # 沿用原本立即标记的行为，下方分支会按通道类型决定是否回填。
    order.updated_at = datetime.utcnow()

    # [支付配置 PRD v1.0] 可选 channel_code：若传入则校验并落库；
    # 未启用通道下单时返回 4001 业务码（HTTP 400）。
    ch_provider: Optional[str] = None
    if data.channel_code:
        from app.models.models import PaymentChannel as _PC
        ch_res = await db.execute(
            select(_PC).where(_PC.channel_code == data.channel_code)
        )
        ch = ch_res.scalar_one_or_none()
        if ch is None:
            raise HTTPException(status_code=400, detail={
                "code": 4001, "message": "该支付方式暂未开通，请选择其他支付方式"
            })
        if not (ch.is_enabled and ch.is_complete):
            raise HTTPException(status_code=400, detail={
                "code": 4001, "message": "该支付方式暂未开通，请选择其他支付方式"
            })
        order.payment_channel_code = ch.channel_code
        order.payment_display_name = ch.display_name
        ch_provider = ch.provider

    # [支付宝 H5 正式接入 v1.0 · 核心改动]
    # 当 channel_code=alipay_h5 时不再立即推进订单状态：
    # 由支付宝异步通知 /api/payment/alipay/notify 收到 TRADE_SUCCESS 后再幂等推进。
    # 其它通道（wechat_app/alipay_app/wechat_miniprogram）保留原行为。
    is_alipay_h5_real = (
        order.payment_channel_code == "alipay_h5" and ch_provider == "alipay"
    )

    pay_url: Optional[str] = None
    if is_alipay_h5_real:
        try:
            pay_url = await _build_alipay_h5_pay_url(order, db)
        except Exception as e:  # noqa: BLE001
            # SDK 未装配 / 配置缺失等场景，记录告警并兜底回退到沙盒桩，
            # 让链路在依赖未就绪时不至于整体不可用。
            logger.warning(
                "alipay_h5 real pay_url build failed, fallback to sandbox: %s", e
            )
            pay_url = _build_sandbox_pay_url(order.order_no, "alipay_h5")
            # 兜底场景下：保持原沙盒桩"立即标记已支付"的行为（开发自测）
            order.paid_at = datetime.utcnow()
            await _advance_status_after_payment(order, db)
        else:
            # 真实支付宝链路：仅记录通道与时间，不立即标记 paid_at；
            # 由 /api/payment/alipay/notify 收到 TRADE_SUCCESS 后再幂等回填。
            order.updated_at = datetime.utcnow()
    else:
        # 非 alipay_h5 通道沿用原"立即推进 + 立即标记 paid_at"逻辑
        order.paid_at = datetime.utcnow()
        await _advance_status_after_payment(order, db)

    await db.commit()

    return {
        "message": "支付成功" if not is_alipay_h5_real else "已生成支付宝收银台 URL，请前往完成支付",
        "order_no": order.order_no,
        "status": _normalize_status(order.status),
        "pay_url": pay_url,
        "channel_code": order.payment_channel_code,
    }


@router.post("/{order_id}/confirm-free")
async def confirm_free_unified_order(
    order_id: int,
    data: ConfirmFreeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[H5 支付链路修复 v1.0] 0 元订单确认入口（不走支付链路）。

    校验：
      1) 订单存在（不存在 → 404）
      2) 订单归属当前用户（否则 → 403 code=forbidden）
      3) 订单处于 pending_payment（否则 → 400 code=invalid_status）
      4) `paid_amount == 0`（否则 → 400 code=not_free_order，**防绕过二次校验**）

    动作：复用 `_advance_status_after_payment` 推进订单状态；不写 PaymentTransaction。
    通道：channel_code 可选；若传入但通道未启用/不完整，**因订单本身已是 0 元**，
    仍允许提交（按方案 §5.3「通道全关时 0 元订单允许 payment_channel_code 为 null」）。
    """
    result = await db.execute(
        select(UnifiedOrder)
        .options(
            selectinload(UnifiedOrder.items).selectinload(OrderItem.product),
            selectinload(UnifiedOrder.store),
        )
        .where(UnifiedOrder.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "无权操作他人订单"
        })

    status_val = order.status
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "pending_payment":
        raise HTTPException(status_code=400, detail={
            "code": "invalid_status", "message": "该订单当前状态无法确认免支付"
        })

    if float(order.paid_amount or 0) != 0:
        raise HTTPException(status_code=400, detail={
            "code": "not_free_order", "message": "非 0 元订单不能走免支付通道"
        })

    order.paid_at = datetime.utcnow()
    # [零元单 v2.2] 0 元单统一标记为"优惠券全额抵扣"，对账与报表口径友好
    order.payment_method = UnifiedPaymentMethod.coupon_deduction

    # 0 元订单允许 channel_code 为 null（"免支付"）；如传入且通道启用完整则落库，
    # 否则静默忽略（不报错），见方案 §5.3。
    if data.channel_code:
        from app.models.models import PaymentChannel as _PC
        ch_res = await db.execute(
            select(_PC).where(_PC.channel_code == data.channel_code)
        )
        ch = ch_res.scalar_one_or_none()
        if ch is not None and ch.is_enabled and ch.is_complete:
            order.payment_channel_code = ch.channel_code
            order.payment_display_name = ch.display_name

    await _advance_status_after_payment(order, db)
    order.updated_at = datetime.utcnow()

    return _build_order_response(order)




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
    """[PRD 订单状态机简化方案 v1.0 + PRD-03 客户端改期能力收口 v1.0] 用户填写预约时间。

    新策略（2026-05-03 起）：
    - 首次填预约日：pending_appointment → **pending_use**（直接跳过 appointed，立即出码）
    - 修改预约日：pending_use 阶段持续允许调整，状态保持不变
    - 兼容历史 appointed：旧订单仍可调用本接口改预约日，状态翻为 pending_use

    PRD-03 角色校验（§2.4 / §R-03-06）：
    - 改期权 100% 归客户端；本接口仅允许 role=user（C 端客户）调用
    - role in (merchant / admin / doctor / content_editor) → 403 Forbidden
    """
    # [PRD-03 §2.4 / §R-03-06] 角色校验：仅允许 customer 角色（即 UserRole.user）调用
    # 注意：项目中 UserRole 枚举值为 user/admin/doctor/merchant/content_editor，
    # 其中 "user" 即 PRD 文档所述的 "customer"（C 端客户）
    role_val = current_user.role
    if hasattr(role_val, "value"):
        role_val = role_val.value
    if str(role_val) != "user":
        raise HTTPException(
            status_code=403,
            detail="无操作权限：改期权仅限客户端，商家/平台无权调用",
        )

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

    # [核销订单过期+改期规则优化 v1.0] 改期上限校验
    # 仅当订单已经有过预约时间（修改预约 = 改约）才计入。首次填预约日不消耗改期次数。
    has_existing_appt = any(getattr(it, "appointment_time", None) for it in (order.items or []))
    rcount = int(getattr(order, "reschedule_count", 0) or 0)
    rlimit = int(getattr(order, "reschedule_limit", 3) or 3)
    if has_existing_appt and rcount >= rlimit:
        raise HTTPException(status_code=400, detail="本订单已达改期上限")

    # [PRD-03 §F-03-6 / §R-03-04] 商品级 allow_reschedule 开关：任一商品禁止改期 → 整单不允许
    # 仅在「真正的改期」（已有过预约时间）时校验；首次填预约日不卡此项
    if has_existing_appt:
        try:
            for it in (order.items or []):
                prod = getattr(it, "product", None)
                if prod is not None:
                    v = getattr(prod, "allow_reschedule", True)
                    if v is False:
                        raise HTTPException(
                            status_code=400,
                            detail="该商品不支持改期",
                        )
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            pass

    # [PRD-03 §F-03-5 / §R-03-03] 改期可选范围：明天起 90 天（仅在改期时校验，首次预约不卡）
    if has_existing_appt:
        from datetime import datetime as _dt
        now_local = _dt.now()
        # 「明天起」：appointment_time 必须 >= 明天 00:00
        tomorrow_start = _dt.combine(
            (now_local.date() + timedelta(days=1)),
            datetime.min.time(),
        )
        max_date = _dt.combine(
            (now_local.date() + timedelta(days=90)),
            datetime.max.time(),
        )
        # 把 appointment_time 视作 naive datetime 比较（前端通常传本地时间）
        appt_naive = data.appointment_time
        if appt_naive.tzinfo is not None:
            appt_naive = appt_naive.replace(tzinfo=None)
        if appt_naive < tomorrow_start:
            raise HTTPException(
                status_code=400,
                detail="改期日期最早从明天起",
            )
        if appt_naive > max_date:
            raise HTTPException(
                status_code=400,
                detail="改期日期最远 90 天内",
            )

    # [PRD-03 §2.5 / §R-03-05] 宽松改期容量校验：仅校验门店营业 + 时段在营业内
    # 不校验单时段容量（允许超约，由门店人工协调）。仅改期时校验。
    if has_existing_appt:
        try:
            from app.utils.reschedule_validator import validate_reschedule_lenient
            store_id_for_validate = getattr(order, "store_id", None)
            valid_res = await validate_reschedule_lenient(
                db,
                store_id=store_id_for_validate,
                appointment_time=data.appointment_time,
            )
            if not valid_res.ok:
                raise HTTPException(
                    status_code=400,
                    detail=valid_res.reason or "目标时段不可改期",
                )
        except HTTPException:
            raise
        except Exception as _e:  # noqa: BLE001
            import logging as _l
            _l.getLogger(__name__).warning(
                "[PRD-03] 改期宽松校验异常（已放行）: %s", _e
            )

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

    # [核销订单过期+改期规则优化 v1.0] 改约（已有过预约时间） → reschedule_count + 1
    prev_appt_time = None
    if has_existing_appt:
        for it in (order.items or []):
            if getattr(it, "appointment_time", None):
                prev_appt_time = it.appointment_time
                break
        order.reschedule_count = rcount + 1

    # [PRD-01 全平台固定时段切片体系 v1.0 · F-01-3]
    # 改期生效后，订单级 time_slot 同步重算并写入；跨日按起始时间归段。
    order.time_slot = _appt_to_slot(data.appointment_time)

    # 关键变化：直接进入 pending_use（立即出码），跳过 appointed
    order.status = UnifiedOrderStatus.pending_use
    order.updated_at = datetime.utcnow()

    # [门店预约看板与改期能力升级 v1.0 · F-11] 改期成功后并行下发三通道通知
    # 仅在「真正的改期」（已存在预约时间）时触发；首次填预约日不触发改期通知
    notify_result = None
    if has_existing_appt:
        try:
            from app.services.reschedule_notification import notify_order_rescheduled
            notify_result = await notify_order_rescheduled(
                db,
                order=order,
                old_appointment_time=prev_appt_time,
                new_appointment_time=data.appointment_time,
            )
        except Exception as _e:  # noqa: BLE001
            import logging as _l
            _l.getLogger(__name__).warning("notify_order_rescheduled 调度失败: %s", _e)

    return {
        "message": "预约已确认",
        "status": "pending_use",
        "appointment_time": data.appointment_time.isoformat(),
        "reschedule_count": int(getattr(order, "reschedule_count", 0) or 0),
        "reschedule_limit": int(getattr(order, "reschedule_limit", 3) or 3),
        "notify_result": notify_result.to_dict() if notify_result else None,
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

    # [订单系统增强 PRD v1.0 F10/R7] 客户在「服务时段开始前任意时间」均可全额取消并退款
    # - 待付款：直接取消
    # - 待预约 / 已预约 / 待核销 / 部分核销：若有预约时间且尚未到达，则放行
    # - 已完成 / 已取消 / 已退款 / 已过期：拒绝
    cancellable_simple = ("pending_payment", "pending_appointment")
    cancellable_with_time = ("appointed", "pending_use")
    rejected_states = (
        "completed", "cancelled", "refunded", "expired",
        "refunding", "partial_used", "pending_review",
    )
    if status_val in rejected_states:
        raise HTTPException(status_code=400, detail="该订单当前状态无法取消")

    if status_val in cancellable_with_time:
        # 校验服务时间未到
        from datetime import datetime as _dt
        appt_time = None
        for it in order.items:
            if it.appointment_time:
                appt_time = it.appointment_time
                break
        if appt_time is not None and appt_time <= _dt.utcnow():
            raise HTTPException(status_code=400, detail="服务时段已开始，不能自助取消，请走「申请退款」流程")
    elif status_val not in cancellable_simple:
        raise HTTPException(status_code=400, detail="该订单无法取消")

    # 已支付订单取消视为「全额退款」：标记 refund_status，金额退回（沿用现有退款链路）
    refund_back = False
    if status_val != "pending_payment":
        refund_back = True

    # [订单核销码状态与未支付超时治理 v1.0] 统一取消出口
    # 同步把所有 OrderItem.redemption_code_status 置为 expired，避免「订单 cancelled / 核销码 active」脏数据
    from app.services.order_cancel import cancel_order_with_items
    await cancel_order_with_items(
        db, order,
        cancel_reason=data.cancel_reason or "客户主动取消",
    )
    if refund_back:
        try:
            order.refund_status = RefundStatusEnum.refunded
        except Exception:  # noqa: BLE001
            pass

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

    # [订单系统增强 PRD v1.0 F7] 触发站内信：订单已取消
    try:
        from app.services.order_notification import notify_order_cancelled
        await notify_order_cancelled(
            db, user_id=current_user.id, order_id=order.id, order_no=order.order_no,
        )
    except Exception as _e:  # noqa: BLE001
        import logging as _l
        _l.getLogger(__name__).warning("notify_order_cancelled 失败：%s", _e)

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
    # [核销订单过期+改期规则优化 v1.0] 已过期订单一律不可退款
    if status_val == "expired":
        raise HTTPException(status_code=400, detail="已过期的订单无法申请退款")
    # 已完成 / 已退款 等终态也不允许重复退款
    if status_val in ("completed", "refunded"):
        raise HTTPException(status_code=400, detail="该订单当前状态不允许申请退款")

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
