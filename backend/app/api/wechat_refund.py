"""[微信小程序支付完整接入 v1.0]

管理后台退款审核与操作接口：
- POST /api/admin/refunds/{refund_id}/approve       审核通过并执行退款
- POST /api/admin/refunds/{refund_id}/reject        审核拒绝
- POST /api/admin/refunds/{refund_id}/retry         退款失败重试
- GET  /api/admin/refunds                           退款列表
- GET  /api/admin/refunds/{refund_id}               退款详情

设计要点：
- 管理员审核通过后调用支付平台退款 API（微信/支付宝）
- 支持全额退款和部分退款
- 退款成功后：订单状态更新为 refunded，核销码全部作废
- 退款金额、退款单号记录到 refund_requests 表
- 退款失败显示原因，支持手动重试
- 链式调用 wechat_pay_service 和 alipay_service
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    OrderItem,
    PaymentChannel,
    RefundRequest,
    RefundRequestStatus,
    RefundStatusEnum,
    UnifiedOrder,
    UnifiedOrderStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/refunds", tags=["管理后台退款"])
admin_dep = require_role("admin")

# 可退款期限 = 支付后 15 天
REFUND_VALID_DAYS = 15


# ─────────────── Body Schema ───────────────

class ApproveRefundBody(BaseModel):
    """退款审批请求体。"""
    refund_amount: Optional[float] = Field(None, description="退款金额（不传则全额退款）")
    admin_notes: Optional[str] = Field(None, description="管理员备注")


class RejectRefundBody(BaseModel):
    """退款驳回请求体。"""
    admin_notes: Optional[str] = Field(None, description="拒绝理由")


class RetryRefundBody(BaseModel):
    """退款重试请求体。"""
    admin_notes: Optional[str] = Field(None, description="重试备注")


# ─────────────── 分页 Schema ───────────────
REFUNDS_PAGE_SIZE = 20


async def _get_runtime_config(db: AsyncSession, channel_code: str) -> dict:
    """从 DB 获取并解密支付通道配置。"""
    from app.api.payment_config import _decrypt_for_runtime

    res = await db.execute(
        select(PaymentChannel).where(PaymentChannel.channel_code == channel_code)
    )
    ch = res.scalar_one_or_none()
    if ch is None:
        raise ValueError(f"未找到支付通道：{channel_code}")
    if not ch.is_enabled or not ch.is_complete:
        raise ValueError(f"支付通道 {channel_code} 未启用或配置不完整")
    return _decrypt_for_runtime(channel_code, ch.config_json or {})


async def _execute_wechat_refund(
    order: UnifiedOrder,
    refund_req: RefundRequest,
    runtime_cfg: dict,
    refund_amount_cents: int,
    total_amount_cents: int,
) -> dict:
    """执行微信支付退款。"""
    from app.services.wechat_pay_service import create_refund as _wechat_refund

    mch_id = runtime_cfg.get("mch_id", "")
    cert_serial_no = runtime_cfg.get("cert_serial_no", "")
    private_key_pem = runtime_cfg.get("private_key", "")

    out_refund_no = f"RF{order.order_no}{_uuid.uuid4().hex[:8]}"
    reason = refund_req.reason or ""

    result = await _wechat_refund(
        out_trade_no=order.order_no,
        out_refund_no=out_refund_no,
        total_amount=total_amount_cents,
        refund_amount=refund_amount_cents,
        reason=reason,
        mch_id=mch_id,
        cert_serial_no=cert_serial_no,
        private_key_pem=private_key_pem,
    )

    if result.get("success"):
        refund_id = result.get("refund_id", "")
        result["out_refund_no"] = out_refund_no
        result["refund_id"] = refund_id
    return result


async def _execute_alipay_refund(
    order: UnifiedOrder,
    refund_req: RefundRequest,
    runtime_cfg: dict,
    refund_amount: Optional[float],
) -> dict:
    """执行支付宝退款（无 db session 版本，实际使用会转到 _via_db）。"""
    return {"success": False, "error_code": "NEED_DB_SESSION", "error_message": "需要传入 db session，请使用 _execute_alipay_refund_via_db"}


async def _process_refund_approval(
    db: AsyncSession,
    refund_req: RefundRequest,
    refund_amount: Optional[Decimal],
    admin_user_id: int,
    admin_notes: Optional[str] = None,
) -> dict:
    """处理退款审核通过并执行退款的核心逻辑。

    Args:
        db: 数据库会话
        refund_req: 退款申请记录
        refund_amount: 审核通过的退款金额（None=全额退款）
        admin_user_id: 操作管理员 ID
        admin_notes: 管理员备注
    """
    # 1. 加载订单及 items
    res = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.id == refund_req.order_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="关联订单不存在")

    # 2. 确定退款金额
    paid_amount = Decimal(str(order.paid_amount or order.total_amount or 0))
    if refund_amount is not None:
        approved_amount = refund_amount
    else:
        approved_amount = paid_amount

    if approved_amount > paid_amount:
        raise HTTPException(
            status_code=400,
            detail=f"退款金额不能超过订单实付金额（¥{paid_amount:.2f}）",
        )

    is_full_refund = approved_amount >= paid_amount
    refund_type = "full" if is_full_refund else "partial"

    # 3. 确定支付通道
    channel_code = getattr(order, "payment_channel_code", None) or ""
    if channel_code.startswith("wechat"):
        channel = "wechat"
        config_code = channel_code
    elif channel_code.startswith("alipay"):
        channel = "alipay"
        config_code = channel_code
    else:
        # 尝试从 payment_method 推断
        pm = getattr(order, "payment_method", None)
        pm_val = pm.value if hasattr(pm, "value") else str(pm) if pm else ""
        if pm_val == "wechat":
            channel = "wechat"
            config_code = "wechat_miniprogram"
        elif pm_val == "alipay":
            channel = "alipay"
            config_code = "alipay_h5"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"无法确定订单的支付通道（channel_code={channel_code}，payment_method={pm_val}）",
            )

    # 4. 获取支付通道配置
    try:
        runtime_cfg = await _get_runtime_config(db, config_code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取支付通道配置失败：{e}")

    # 5. 执行退款
    result: dict[str, Any]
    if channel == "wechat":
        total_amount_cents = int(paid_amount * 100)
        refund_amount_cents = int(approved_amount * 100)
        result = await _execute_wechat_refund(
            order=order,
            refund_req=refund_req,
            runtime_cfg=runtime_cfg,
            refund_amount_cents=refund_amount_cents,
            total_amount_cents=total_amount_cents,
        )
    elif channel == "alipay":
        result = await _execute_alipay_refund_via_db(
            db=db,
            order=order,
            refund_req=refund_req,
            approved_amount=float(approved_amount),
            is_full_refund=is_full_refund,
        )
    else:
        raise HTTPException(status_code=400, detail=f"不支持的支付渠道：{channel}")

    # 6. 更新退款记录
    refund_req.refund_amount_approved = approved_amount
    refund_req.refund_type = refund_type
    refund_req.refund_channel = channel
    refund_req.admin_user_id = admin_user_id
    if admin_notes:
        refund_req.admin_notes = admin_notes
    refund_req.updated_at = datetime.now()

    if result.get("success"):
        refund_req.status = RefundRequestStatus.completed
        refund_req.refund_transaction_id = result.get("refund_id") or result.get("out_refund_no", "")
        refund_req.updated_at = datetime.now()

        # 7. 更新订单状态
        order.refund_status = RefundStatusEnum.refund_success
        order.status = UnifiedOrderStatus.refunded
        order.updated_at = datetime.now()

        # 8. 所有核销码作废
        for item in order.items:
            if hasattr(item, "redemption_code_status"):
                item.redemption_code_status = "refunded"
                item.updated_at = datetime.now()

        await db.commit()
        return {
            "success": True,
            "message": "退款成功",
            "refund_id": refund_req.id,
            "refund_transaction_id": refund_req.refund_transaction_id,
            "refund_type": refund_type,
            "refund_amount": float(approved_amount),
            "channel": channel,
        }
    else:
        refund_req.status = RefundRequestStatus.approved
        refund_req.updated_at = datetime.now()
        await db.commit()
        error_msg = result.get("error_message", "未知错误")
        error_code = result.get("error_code", "UNKNOWN")
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"退款调用失败：{error_msg}",
                "error_code": error_code,
                "refund_id": refund_req.id,
            },
        )


async def _execute_alipay_refund_via_db(
    db: AsyncSession,
    order: UnifiedOrder,
    refund_req: RefundRequest,
    approved_amount: float,
    is_full_refund: bool,
) -> dict:
    """通过 DB session 获取支付宝客户端并执行退款。"""
    from app.services.alipay_service import (
        create_refund as _alipay_refund,
        get_alipay_client_for_channel,
    )

    client, _ch = await get_alipay_client_for_channel(db, channel_code="alipay_h5")

    out_request_no = f"RF{order.order_no}{_uuid.uuid4().hex[:8]}"
    reason = refund_req.reason or ""

    result = _alipay_refund(
        client=client,
        out_trade_no=order.order_no,
        out_request_no=out_request_no,
        refund_amount=approved_amount if not is_full_refund else None,
        refund_reason=reason,
    )
    return result
# ─────────────── API 端点 ───────────────


@router.get("")
async def list_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(REFUNDS_PAGE_SIZE, ge=1, le=100),
    status: Optional[str] = Query(None, description="退款状态筛选"),
    channel: Optional[str] = Query(None, description="退款渠道筛选"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    """获取退款申请列表（管理员）。"""
    from sqlalchemy import func

    query = select(RefundRequest).options(
        selectinload(RefundRequest.order),
        selectinload(RefundRequest.user),
    )
    count_query = select(func.count(RefundRequest.id))

    if status:
        query = query.where(RefundRequest.status == status)
        count_query = count_query.where(RefundRequest.status == status)

    if channel:
        query = query.where(RefundRequest.refund_channel == channel)
        count_query = count_query.where(RefundRequest.refund_channel == channel)

    total = (await db.execute(count_query)).scalar() or 0

    result = await db.execute(
        query
        .order_by(RefundRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.scalars().all()

    items = []
    for rr in rows:
        order_data = None
        if rr.order:
            o = rr.order
            order_data = {
                "id": o.id,
                "order_no": o.order_no,
                "total_amount": float(o.total_amount or 0),
                "paid_amount": float(o.paid_amount or 0),
                "status": o.status.value if hasattr(o.status, "value") else o.status,
                "refund_status": o.refund_status.value if hasattr(o.refund_status, "value") else o.refund_status,
            }
        user_data = None
        if rr.user:
            user_data = {
                "id": rr.user.id,
                "nickname": rr.user.nickname,
                "phone": rr.user.phone,
            }

        items.append({
            "id": rr.id,
            "order_id": rr.order_id,
            "order_item_id": rr.order_item_id,
            "user_id": rr.user_id,
            "reason": rr.reason,
            "refund_amount": float(rr.refund_amount or 0),
            "refund_amount_approved": float(rr.refund_amount_approved) if rr.refund_amount_approved else None,
            "status": rr.status.value if hasattr(rr.status, "value") else rr.status,
            "refund_transaction_id": rr.refund_transaction_id,
            "refund_type": rr.refund_type,
            "refund_channel": rr.refund_channel,
            "admin_notes": rr.admin_notes,
            "has_redemption": bool(rr.has_redemption),
            "created_at": rr.created_at.isoformat() if rr.created_at else None,
            "updated_at": rr.updated_at.isoformat() if rr.updated_at else None,
            "order": order_data,
            "user": user_data,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{refund_id}")
async def get_refund_detail(
    refund_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    """获取单条退款详情。"""
    res = await db.execute(
        select(RefundRequest)
        .options(
            selectinload(RefundRequest.order).selectinload(UnifiedOrder.items),
            selectinload(RefundRequest.user),
            selectinload(RefundRequest.admin),
        )
        .where(RefundRequest.id == refund_id)
    )
    rr = res.scalar_one_or_none()
    if not rr:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    order_data = None
    if rr.order:
        o = rr.order
        items_data = []
        for item in (o.items or []):
            items_data.append({
                "id": item.id,
                "product_name": item.product_name,
                "product_price": float(item.product_price or 0),
                "quantity": item.quantity,
                "subtotal": float(item.subtotal or 0),
                "redemption_code_status": item.redemption_code_status,
            })
        order_data = {
            "id": o.id,
            "order_no": o.order_no,
            "total_amount": float(o.total_amount or 0),
            "paid_amount": float(o.paid_amount or 0),
            "status": o.status.value if hasattr(o.status, "value") else o.status,
            "refund_status": o.refund_status.value if hasattr(o.refund_status, "value") else o.refund_status,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "payment_channel_code": o.payment_channel_code,
            "items": items_data,
        }

    return {
        "id": rr.id,
        "order_id": rr.order_id,
        "order_item_id": rr.order_item_id,
        "user_id": rr.user_id,
        "reason": rr.reason,
        "refund_amount": float(rr.refund_amount or 0),
        "refund_amount_approved": float(rr.refund_amount_approved) if rr.refund_amount_approved else None,
        "status": rr.status.value if hasattr(rr.status, "value") else rr.status,
        "refund_transaction_id": rr.refund_transaction_id,
        "refund_type": rr.refund_type,
        "refund_channel": rr.refund_channel,
        "admin_notes": rr.admin_notes,
        "admin_user_id": rr.admin_user_id,
        "has_redemption": bool(rr.has_redemption),
        "return_tracking_number": rr.return_tracking_number,
        "return_tracking_company": rr.return_tracking_company,
        "created_at": rr.created_at.isoformat() if rr.created_at else None,
        "updated_at": rr.updated_at.isoformat() if rr.updated_at else None,
        "order": order_data,
        "user": {"id": rr.user.id, "nickname": rr.user.nickname, "phone": rr.user.phone} if rr.user else None,
        "admin": {"id": rr.admin.id, "nickname": rr.admin.nickname} if rr.admin else None,
    }


@router.post("/{refund_id}/approve")
async def approve_refund(
    refund_id: int,
    data: ApproveRefundBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(admin_dep),
):
    """管理员审核通过退款并执行退款。"""
    res = await db.execute(
        select(RefundRequest)
        .options(selectinload(RefundRequest.order))
        .where(RefundRequest.id == refund_id)
    )
    refund_req = res.scalar_one_or_none()
    if not refund_req:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    if refund_req.status not in (RefundRequestStatus.pending, RefundRequestStatus.reviewing):
        raise HTTPException(status_code=400, detail="该退款申请当前状态不允许审核通过")

    approved_amount = Decimal(str(data.refund_amount)) if data.refund_amount is not None else None

    return await _process_refund_approval(
        db=db,
        refund_req=refund_req,
        refund_amount=approved_amount,
        admin_user_id=current_user.id,
        admin_notes=data.admin_notes,
    )


@router.post("/{refund_id}/reject")
async def reject_refund(
    refund_id: int,
    data: RejectRefundBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(admin_dep),
):
    """管理员拒绝退款申请。"""
    res = await db.execute(
        select(RefundRequest)
        .where(RefundRequest.id == refund_id)
    )
    refund_req = res.scalar_one_or_none()
    if not refund_req:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    if refund_req.status not in (RefundRequestStatus.pending, RefundRequestStatus.reviewing):
        raise HTTPException(status_code=400, detail="该退款申请当前状态不允许拒绝")

    refund_req.status = RefundRequestStatus.rejected
    refund_req.admin_user_id = current_user.id
    refund_req.admin_notes = data.admin_notes
    refund_req.updated_at = datetime.now()

    # 恢复订单的退款状态
    order_res = await db.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == refund_req.order_id)
    )
    order = order_res.scalar_one_or_none()
    if order:
        order.refund_status = RefundStatusEnum.rejected
        order.updated_at = datetime.now()

    await db.commit()
    return {"message": "退款申请已拒绝", "refund_id": refund_id}


@router.post("/{refund_id}/retry")
async def retry_refund(
    refund_id: int,
    data: RetryRefundBody = Depends(lambda: RetryRefundBody()),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(admin_dep),
):
    """退款失败后手动重试。"""
    res = await db.execute(
        select(RefundRequest)
        .options(selectinload(RefundRequest.order))
        .where(RefundRequest.id == refund_id)
    )
    refund_req = res.scalar_one_or_none()
    if not refund_req:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    if refund_req.status == RefundRequestStatus.completed:
        raise HTTPException(status_code=400, detail="该退款已成功完成，无需重试")

    approved_amount = refund_req.refund_amount_approved or refund_req.refund_amount

    return await _process_refund_approval(
        db=db,
        refund_req=refund_req,
        refund_amount=approved_amount,
        admin_user_id=current_user.id,
        admin_notes=data.admin_notes or "手动重试",
    )
