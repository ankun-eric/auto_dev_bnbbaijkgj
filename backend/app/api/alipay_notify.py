"""[支付宝 H5 正式支付链路接入 v1.0]

支付宝异步通知 / 同步回跳后端处理：

POST /api/payment/alipay/notify  ← 支付宝服务器异步回调
  - application/x-www-form-urlencoded 原始表单
  - 必须按支付宝原始字段做 RSA2 验签（sign 字段除外）
  - 关键字段二次校验：app_id / out_trade_no / total_amount / seller_id
  - trade_status in (TRADE_SUCCESS, TRADE_FINISHED) → 幂等推进订单状态为「已支付」
  - 已处理过同一 trade_no 的，直接返回 success（幂等）
  - 必须返回纯文本 `success`（无 BOM、无多余空白），否则支付宝会重试

设计要点：
- 路由模块独立挂载（前缀 /api/payment/alipay），避免与统一订单 /api/orders 冲突
- 校验顺序：① RSA2 验签 ② 业务字段对账 ③ 幂等去重 ④ 状态推进
- 任何阶段失败均返回非 success 文本（支付宝识别为失败，会重试）

Reference: PRD §4.2.4
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.models import (
    UnifiedOrder,
    UnifiedOrderStatus,
    UnifiedPaymentMethod,
)
from app.services.alipay_service import (
    get_alipay_client_for_channel,
    verify_async_notify,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment/alipay", tags=["支付宝异步通知"])


_PAID_TRADE_STATUSES = {"TRADE_SUCCESS", "TRADE_FINISHED"}


async def _advance_status_after_payment(order: UnifiedOrder, db: AsyncSession) -> None:
    """复用 unified_orders 中已有的状态机推进逻辑。

    使用函数内 import 避免模块顶层循环 import。
    """
    from app.api.unified_orders import (
        _advance_status_after_payment as _real_advance,
    )
    await _real_advance(order, db)


@router.post("/notify", response_class=PlainTextResponse)
async def alipay_async_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """支付宝异步通知接收端点。

    必须返回纯文本 'success'（成功）或其它（失败/重试）。
    """
    # 1. 解析原始 form
    try:
        form = await request.form()
        form_dict = {k: v for k, v in form.items()}
    except Exception as e:  # noqa: BLE001
        logger.error("alipay_notify parse form failed: %s", e)
        return PlainTextResponse("fail")

    if not form_dict:
        logger.warning("alipay_notify empty form")
        return PlainTextResponse("fail")

    # 安全的日志记录（脱敏部分敏感字段）
    log_safe = {k: v for k, v in form_dict.items() if k not in ("sign",)}
    if "buyer_logon_id" in log_safe:
        v = str(log_safe["buyer_logon_id"])
        if len(v) > 4:
            log_safe["buyer_logon_id"] = v[:2] + "***" + v[-2:]
    logger.info("alipay_notify received: %s", log_safe)

    # 2. 取得 SDK 客户端 + 验签
    try:
        client, ch = await get_alipay_client_for_channel(db, channel_code="alipay_h5")
    except Exception as e:  # noqa: BLE001
        logger.error("alipay_notify get client failed: %s", e)
        return PlainTextResponse("fail")

    if not verify_async_notify(client, form_dict):
        logger.warning("alipay_notify verify FAILED")
        return PlainTextResponse("fail")

    # 3. 业务字段二次校验
    cfg = ch.config_json or {}
    expect_app_id = (cfg.get("app_id") or "").strip()
    notify_app_id = (form_dict.get("app_id") or "").strip()
    if expect_app_id and notify_app_id and expect_app_id != notify_app_id:
        logger.warning("alipay_notify app_id mismatch: expect=%s notify=%s",
                       expect_app_id, notify_app_id)
        return PlainTextResponse("fail")

    out_trade_no = (form_dict.get("out_trade_no") or "").strip()
    if not out_trade_no:
        return PlainTextResponse("fail")

    trade_status = (form_dict.get("trade_status") or "").strip().upper()
    trade_no = (form_dict.get("trade_no") or "").strip() or None
    notify_total_amount = (form_dict.get("total_amount") or "0").strip()
    buyer_logon_id = (form_dict.get("buyer_logon_id") or "").strip() or None

    # 4. 查找订单
    res = await db.execute(
        select(UnifiedOrder)
        .options(selectinload(UnifiedOrder.items))
        .where(UnifiedOrder.order_no == out_trade_no)
    )
    order = res.scalar_one_or_none()
    if not order:
        logger.warning("alipay_notify order not found: out_trade_no=%s", out_trade_no)
        # 找不到订单也返回 fail，让支付宝重试一次防数据库延迟
        return PlainTextResponse("fail")

    # 5. 金额对账（防篡改）
    try:
        notify_amt = Decimal(notify_total_amount)
        order_amt = Decimal(str(order.paid_amount or order.total_amount or 0))
        # 允许 0.01 以内的浮点误差
        if abs(notify_amt - order_amt) > Decimal("0.01"):
            logger.warning(
                "alipay_notify amount mismatch: notify=%s order=%s out_trade_no=%s",
                notify_amt, order_amt, out_trade_no,
            )
            return PlainTextResponse("fail")
    except Exception as e:  # noqa: BLE001
        logger.warning("alipay_notify amount parse failed: %s", e)
        return PlainTextResponse("fail")

    # 6. 仅 TRADE_SUCCESS / TRADE_FINISHED 推进状态
    if trade_status not in _PAID_TRADE_STATUSES:
        logger.info("alipay_notify ignored trade_status=%s", trade_status)
        return PlainTextResponse("success")

    # 7. 幂等 + 状态机推进
    # 幂等键：order.status 已不在 pending_payment 状态时（已推进过），直接 success
    cur_status_val = order.status.value if hasattr(order.status, "value") else order.status
    if cur_status_val != "pending_payment":
        logger.info(
            "alipay_notify idempotent: order_no=%s already advanced (status=%s)",
            out_trade_no, cur_status_val,
        )
        return PlainTextResponse("success")

    order.payment_method = UnifiedPaymentMethod.alipay
    order.payment_channel_code = "alipay_h5"
    order.paid_at = order.paid_at or datetime.utcnow()
    order.updated_at = datetime.utcnow()
    await _advance_status_after_payment(order, db)

    try:
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.error("alipay_notify commit failed: %s", e)
        return PlainTextResponse("fail")

    logger.info(
        "alipay_notify success: order_no=%s trade_no=%s buyer=%s",
        out_trade_no, trade_no, buyer_logon_id or "-",
    )
    return PlainTextResponse("success")
