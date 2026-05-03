"""[支付配置 PRD v1.0] C 端公开支付方式查询接口。

- GET /api/pay/available-methods?platform=miniprogram|h5|app
  返回该端已启用且配置完整的通道列表；APP 端固定 微信(10) → 支付宝(20)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import PaymentChannel
from app.schemas.payment_config import AvailableMethodItem

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
