"""[支付配置 PRD v1.0] C 端公开支付方式查询接口。

- GET /api/pay/available-methods?platform=miniprogram|h5|app
  返回该端已启用且配置完整的通道列表；APP 端固定 微信(10) → 支付宝(20)。
- POST /api/pay/wechat/jsapi-order  JSAPI 下单 + 生成小程序调起签名参数包
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import PaymentChannel
from app.schemas.payment_config import AvailableMethodItem


class JsapiOrderRequest(BaseModel):
    """JSAPI 下单请求体。"""
    order_id: int = Field(..., description="统一订单 ID")
    openid: str = Field(..., description="微信用户 openid")

router = APIRouter(prefix="/api/pay", tags=["支付公开"])


_VALID_PLATFORMS = {"miniprogram", "h5", "app"}


@router.get("/available-methods", response_model=list[AvailableMethodItem])
async def available_methods(
    platform: str = Query(..., description="目标端：miniprogram / h5 / app"),
    db: AsyncSession = Depends(get_db),
):
    if platform not in _VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail="platform 取值必须是 miniprogram / h5 / app")
    res = await db.execute(
        select(PaymentChannel)
        .where(
            PaymentChannel.platform == platform,
            PaymentChannel.is_enabled == True,  # noqa: E712
            PaymentChannel.is_complete == True,  # noqa: E712
        )
        .order_by(PaymentChannel.sort_order, PaymentChannel.id)
    )
    rows = res.scalars().all()
    return [
        AvailableMethodItem(
            channel_code=r.channel_code,
            display_name=r.display_name,
            provider=r.provider,
            sort_order=r.sort_order or 0,
        )
        for r in rows
    ]


# [微信小程序支付完整接入 v1.0] JSAPI 下单接口
@router.post("/wechat/jsapi-order")
async def wechat_jsapi_order(
    data: JsapiOrderRequest,
    db: AsyncSession = Depends(get_db),
):
    """为微信小程序生成 JSAPI 下单参数。

    调用微信支付 /v3/pay/transactions/jsapi 生成 prepay_id，
    返回小程序调起支付所需的签名参数包。

    前端使用此返回调用 wx.requestPayment()。
    """
    import logging as _log
    import os as _os
    from app.models.models import UnifiedOrder
    from app.services.wechat_pay_service import (
        create_jsapi_order,
        generate_pay_sign,
    )
    from app.api.payment_config import _decrypt_for_runtime

    _logger = _log.getLogger(__name__)

    order_id = data.order_id
    openid = data.openid

    # 1. 查找订单
    res = await db.execute(
        select(UnifiedOrder).where(UnifiedOrder.id == order_id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    status_val = order.status.value if hasattr(order.status, "value") else order.status
    if status_val != "pending_payment":
        raise HTTPException(status_code=400, detail="该订单状态不允许支付")

    paid_amount = float(order.paid_amount or order.total_amount or 0)
    if paid_amount <= 0:
        raise HTTPException(status_code=400, detail="0 元订单无需支付")

    total_cents = int(paid_amount * 100)

    # 2. 获取微信支付配置
    ch_res = await db.execute(
        select(PaymentChannel).where(PaymentChannel.channel_code == "wechat_miniprogram")
    )
    ch = ch_res.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=400, detail="微信小程序支付通道未配置")
    if not ch.is_enabled or not ch.is_complete:
        raise HTTPException(status_code=400, detail="微信小程序支付通道未启用或配置不完整")

    runtime_cfg = _decrypt_for_runtime("wechat_miniprogram", ch.config_json or {})

    mch_id = runtime_cfg.get("mch_id", "")
    cert_serial_no = runtime_cfg.get("cert_serial_no", "")
    private_key_pem = runtime_cfg.get("private_key", "")
    appid = runtime_cfg.get("appid", "")

    # 3. 构造 notify_url
    base = _os.environ.get("PUBLIC_API_BASE_URL", "").rstrip("/")
    notify_url = f"{base}/api/pay/notify/wechat_miniprogram"

    # 4. 获取描述
    description = "宾尼健康订单"
    if order.items:
        description = order.items[0].product_name or description
    description = description[:127]

    # 5. 调用 JSAPI 下单
    result = await create_jsapi_order(
        out_trade_no=order.order_no,
        total_amount=total_cents,
        description=description,
        openid=openid,
        notify_url=notify_url,
        mch_id=mch_id,
        cert_serial_no=cert_serial_no,
        private_key_pem=private_key_pem,
        appid=appid,
    )

    if not result.get("success"):
        error_msg = result.get("error_message", "未知错误")
        error_code = result.get("error_code", "UNKNOWN")
        _logger.error(
            "wechat_jsapi_order failed: order_no=%s error=%s code=%s",
            order.order_no, error_msg, error_code,
        )
        raise HTTPException(
            status_code=400,
            detail={"message": f"微信支付下单失败：{error_msg}", "error_code": error_code},
        )

    prepay_id = result.get("prepay_id", "")

    # 6. 生成小程序调起支付签名参数包
    pay_params = generate_pay_sign(
        prepay_id=prepay_id,
        appid=appid,
        private_key_pem=private_key_pem,
    )

    # 7. 更新订单通道信息
    order.payment_channel_code = "wechat_miniprogram"
    order.payment_method = "wechat"
    order.payment_display_name = "微信支付"
    order.updated_at = datetime.now()
    await db.commit()

    return {
        "prepay_id": prepay_id,
        "order_no": order.order_no,
        "pay_params": pay_params,
    }
