"""[微信小程序支付完整接入 v1.0]

微信支付异步回调通知处理：
- POST /api/pay/notify/wechat_miniprogram

设计要点：
- 验签：使用微信支付平台证书公钥验证回调签名（从 HTTP 头 Wechatpay-Signature 等获取）
- 解密：使用 API v3 密钥解密回调报文（AEAD_AES_256_GCM）
- 订单状态更新：根据回调中的 trade_state 更新订单支付状态为 paid
- 幂等处理：同一 out_trade_no 重复回调不重复处理（已在 paid 状态则直接返回 success）
- 返回应答：处理成功后返回 JSON {"code": "SUCCESS", "message": "成功"}，HTTP 200
- 验签失败返回 400/500

Reference: 微信支付 API v3 回调通知文档
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.models import (
    UnifiedOrder,
    UnifiedOrderStatus,
    UnifiedPaymentMethod,
)
from app.services.wechat_pay_service import (
    decrypt_callback_resource,
    ensure_platform_certificates,
    verify_callback_sign,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pay/notify", tags=["微信支付异步通知"])

# 支付成功状态
_PAID_TRADE_STATES = {"SUCCESS", "REFUND"}


async def _get_wechat_runtime_config(db: AsyncSession) -> dict:
    """从 DB 获取并解密微信小程序支付通道配置。"""
    from app.models.models import PaymentChannel
    from app.api.payment_config import _decrypt_for_runtime

    res = await db.execute(
        select(PaymentChannel).where(
            PaymentChannel.channel_code == "wechat_miniprogram"
        )
    )
    ch = res.scalar_one_or_none()
    if ch is None:
        raise ValueError("未找到微信小程序支付通道")
    if not ch.is_enabled or not ch.is_complete:
        raise ValueError("微信小程序支付通道未启用或配置不完整")

    return _decrypt_for_runtime("wechat_miniprogram", ch.config_json or {})


async def _advance_status_after_payment(order: UnifiedOrder, db: AsyncSession) -> None:
    """复用 unified_orders 中已有的状态机推进逻辑。"""
    from app.api.unified_orders import (
        _advance_status_after_payment as _real_advance,
    )
    await _real_advance(order, db)


@router.post("/wechat_miniprogram")
async def wechat_miniprogram_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """微信小程序支付异步通知接收端点。

    HTTP 头包含签名信息：
    - Wechatpay-Signature: 签名值
    - Wechatpay-Serial: 证书序列号
    - Wechatpay-Timestamp: 时间戳
    - Wechatpay-Nonce: 随机串

    请求体示例：
    {
        "id": "...",
        "create_time": "...",
        "resource_type": "encrypt-resource",
        "event_type": "TRANSACTION.SUCCESS",
        "summary": "...",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": "...",
            "associated_data": "",
            "nonce": "...",
            "original_type": "transaction"
        }
    }
    """
    # 1. 获取 HTTP 头签名信息
    wechatpay_signature = request.headers.get("Wechatpay-Signature", "")
    wechatpay_serial = request.headers.get("Wechatpay-Serial", "")
    wechatpay_timestamp = request.headers.get("Wechatpay-Timestamp", "")
    wechatpay_nonce = request.headers.get("Wechatpay-Nonce", "")

    if not all([wechatpay_signature, wechatpay_serial, wechatpay_timestamp, wechatpay_nonce]):
        logger.warning("wechat_notify missing required headers")
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "缺少签名头"},
        )

    # 2. 读取请求体
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
    except Exception as e:
        logger.error("wechat_notify read body failed: %s", e)
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "读取请求体失败"},
        )

    # 3. 获取微信支付配置
    try:
        runtime_cfg = await _get_wechat_runtime_config(db)
    except Exception as e:
        logger.error("wechat_notify get config failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": f"获取配置失败: {e}"},
        )

    mch_id = runtime_cfg.get("mch_id", "")
    api_v3_key = runtime_cfg.get("api_v3_key", "")
    cert_serial_no = runtime_cfg.get("cert_serial_no", "")
    private_key_pem = runtime_cfg.get("private_key", "")

    if not api_v3_key:
        logger.error("wechat_notify api_v3_key is empty")
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": "API v3 密钥未配置"},
        )

    # 4. 确保平台证书已缓存
    try:
        await ensure_platform_certificates(
            mch_id=mch_id,
            cert_serial_no=cert_serial_no,
            private_key_pem=private_key_pem,
            api_v3_key=api_v3_key,
        )
    except Exception as e:
        logger.warning("wechat_notify ensure_platform_certificates failed, try cached: %s", e)

    # 5. 验签
    try:
        sign_ok = verify_callback_sign(
            timestamp=wechatpay_timestamp,
            nonce_str=wechatpay_nonce,
            body=body_str,
            signature=wechatpay_signature,
            serial_no=wechatpay_serial,
        )
    except Exception as e:
        logger.error("wechat_notify verify_callback_sign exception: %s", e)
        sign_ok = False

    if not sign_ok:
        # 验签失败可能因为证书过期，尝试刷新后重试一次
        try:
            await ensure_platform_certificates(
                mch_id=mch_id,
                cert_serial_no=cert_serial_no,
                private_key_pem=private_key_pem,
                api_v3_key=api_v3_key,
            )
            sign_ok = verify_callback_sign(
                timestamp=wechatpay_timestamp,
                nonce_str=wechatpay_nonce,
                body=body_str,
                signature=wechatpay_signature,
                serial_no=wechatpay_serial,
            )
        except Exception as e:
            logger.error("wechat_notify retry verify failed: %s", e)

    if not sign_ok:
        logger.warning("wechat_notify 验签失败")
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "验签失败"},
        )

    # 6. 解析回调 JSON
    import json as _json
    try:
        callback_data = _json.loads(body_str)
    except Exception as e:
        logger.error("wechat_notify parse JSON failed: %s", e)
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "JSON 解析失败"},
        )

    # 7. 解密 resource
    resource = callback_data.get("resource", {})
    event_type = callback_data.get("event_type", "")

    ciphertext = resource.get("ciphertext", "")
    nonce = resource.get("nonce", "")
    associated_data = resource.get("associated_data", "") or ""

    if not ciphertext:
        logger.warning("wechat_notify empty ciphertext, event_type=%s", event_type)
        return JSONResponse(
            status_code=200,
            content={"code": "SUCCESS", "message": "空报文"},
        )

    try:
        decrypted = decrypt_callback_resource(
            ciphertext=ciphertext,
            nonce=nonce,
            associated_data=str(associated_data),
            api_v3_key=api_v3_key,
        )
    except Exception as e:
        logger.error("wechat_notify decrypt failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": f"解密失败: {e}"},
        )

    logger.info("wechat_notify decrypted resource: %s", _json.dumps(decrypted, ensure_ascii=False, default=str))

    # 8. 提取业务字段
    out_trade_no = decrypted.get("out_trade_no", "")
    trade_state = decrypted.get("trade_state", "")
    transaction_id = decrypted.get("transaction_id", "")
    trade_type = decrypted.get("trade_type", "")

    if not out_trade_no:
        logger.warning("wechat_notify no out_trade_no in decrypted data")
        return JSONResponse(
            status_code=200,
            content={"code": "SUCCESS", "message": "无订单号"},
        )

    # 9. 查找订单
    res = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.order_no == out_trade_no)
    )
    order = res.scalar_one_or_none()
    if not order:
        logger.warning("wechat_notify order not found: out_trade_no=%s", out_trade_no)
        return JSONResponse(
            status_code=200,
            content={"code": "SUCCESS", "message": "订单不存在"},
        )

    # 10. 检查交易状态
    if trade_state not in _PAID_TRADE_STATES:
        logger.info(
            "wechat_notify ignored trade_state=%s for out_trade_no=%s",
            trade_state, out_trade_no,
        )
        return JSONResponse(
            status_code=200,
            content={"code": "SUCCESS", "message": "非支付成功状态"},
        )

    # 11. 幂等处理
    cur_status_val = (
        order.status.value if hasattr(order.status, "value") else order.status
    )

    # 如果订单已不在 pending_payment，说明已经处理过
    if cur_status_val != "pending_payment":
        logger.info(
            "wechat_notify idempotent: order_no=%s already advanced (status=%s)",
            out_trade_no, cur_status_val,
        )
        # 如果 payment_method / channel_code 与回调不一致，矫正（与支付宝保持一致逻辑）
        need_pm_fix = (
            order.payment_method != UnifiedPaymentMethod.wechat
            or order.payment_channel_code != "wechat_miniprogram"
        )
        if need_pm_fix:
            logger.warning(
                "wechat_notify 订单 %s 状态已推进，但 payment_method=%s/channel_code=%s 不一致，矫正",
                out_trade_no,
                order.payment_method,
                order.payment_channel_code,
            )
            order.payment_method = UnifiedPaymentMethod.wechat
            order.payment_channel_code = "wechat_miniprogram"
            order.updated_at = datetime.utcnow()
            try:
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error("wechat_notify pm-fix commit failed: %s", e)
                return JSONResponse(
                    status_code=500,
                    content={"code": "FAIL", "message": "更新失败"},
                )

        return JSONResponse(
            status_code=200,
            content={"code": "SUCCESS", "message": "成功"},
        )

    # 12. 推进订单状态
    order.payment_method = UnifiedPaymentMethod.wechat
    order.payment_channel_code = "wechat_miniprogram"
    order.paid_at = order.paid_at or datetime.utcnow()
    order.updated_at = datetime.utcnow()

    await _advance_status_after_payment(order, db)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("wechat_notify commit failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": "更新订单失败"},
        )

    logger.info(
        "wechat_notify success: order_no=%s transaction_id=%s trade_state=%s",
        out_trade_no, transaction_id, trade_state,
    )

    return JSONResponse(
        status_code=200,
        content={"code": "SUCCESS", "message": "成功"},
    )
